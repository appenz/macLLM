# Parallel Tab Execution

## Motivation

Today, only one conversation tab can have an active agent at a time. Tab switching, new tab creation, and tab closure are all blocked while an agent is running. This prevents the user from starting a query in one tab and switching to another to work on something else while the first query completes.

The goal is to allow multiple conversations to run agents simultaneously, with a clean architecture where tools and subagents are completely isolated from multi-threading complexity.

## Design Principles

1. **The Conversation is the API.** The agent writes to a Conversation. The UI renders a Conversation. There is no other shared state between agent and UI.
2. **Tools are thread-unaware.** Tools call the same functions as today. Thread-local routing underneath delivers them to the correct conversation, but tools never see threading primitives.
3. **The UI is a pure renderer.** It reads conversation state and renders it. The only signal from the agent runtime to the UI is a generic "repaint" callback. The UI never blocks agent execution (except by design when the agent waits for human input like shell approval).
4. **Each conversation is self-contained.** All agent runtime state (thread, abort event, pending approval, token counts) lives on the Conversation object, not on the application coordinator.

## Per-Conversation State Model

### State that moves from MacLLM to Conversation

Today `MacLLM` owns agent-run state globally and processes requests through `handle_instructions()`. All of this moves into `Conversation`, with `Conversation.submit(query)` as the new entry point. The UI calls `submit()` directly — `MacLLM` is no longer in the request processing path.


| Field              | Current owner        | New owner           |
| ------------------ | -------------------- | ------------------- |
| `_agent_thread`    | `MacLLM`             | `Conversation`      |
| `_abort_event`     | `MacLLM`             | `Conversation`      |
| `status_manager`   | `MacLLM`             | removed (see below) |
| `llm_metadata`     | `MacLLM`             | `Conversation`      |
| `pending_approval` | `AgentStatusManager` | `Conversation`      |


New fields on `Conversation`:

```python
class Conversation:
    def __init__(self):
        # ... existing fields ...
        self.agent_thread: threading.Thread | None = None
        self.abort_event: threading.Event = threading.Event()
        self.llm_metadata: dict = {'input_tokens': 0, 'output_tokens': 0}
        self.pending_approval: PendingApproval | None = None  # transient, not persisted

    def is_agent_running(self) -> bool:
        return self.agent_thread is not None and self.agent_thread.is_alive()
```

### AgentStatusManager removal

`AgentStatusManager` is removed entirely. Its responsibilities are absorbed:

- **Plan text**: no longer displayed. The plan lives in `agent.memory.steps` (as `PlanningStep` objects) and can be rendered from there if ever needed again.
- **Tool call progress**: rendered directly from `agent.memory.steps`. Each `ActionStep` contains `tool_calls` (name, arguments, id), `observations` (tool output), and `error` (if failed). An `ActionStep` with `tool_calls` but no `observations` yet means the tool is currently running.
- **Managed-agent nesting**: visible from `TaskStep` entries in `memory.steps`.
- **Pending approval**: moved to `Conversation.pending_approval`.

Tools no longer call `start_tool_call()`, `complete_tool_call()`, or `fail_tool_call()`. They simply do their work and return. The UI reads the result from `memory.steps` after the step callback fires.

The step callback's only remaining job is token accounting (updating `conversation.llm_metadata`) and calling `request_update()`.

### Status indicator removal

The menu bar status indicator (colored circle) is removed. The menu bar shows a static "LLM" label. Per-tab running state is conveyed by a visual indicator on the tab itself (see UI rendering below).

## Thread-Local Conversation Context

### The problem

Tools reach the current conversation through `MacLLM._instance.chat_history`, but `chat_history` points to whatever tab is displayed, not the tab whose agent is running.

### The solution

A `threading.local()` stores the active conversation for each agent thread. Before the agent thread starts, the conversation is set on the thread-local. A central lookup function checks thread-local first, falling back to `MacLLM._instance.chat_history` (for main-thread callers like tag plugins).

```python
_thread_context = threading.local()

def set_current_conversation(conv: Conversation):
    _thread_context.conversation = conv

def get_current_conversation() -> Conversation:
    conv = getattr(_thread_context, 'conversation', None)
    if conv is not None:
        return conv
    from macllm.macllm import MacLLM
    return MacLLM._instance.chat_history
```

This lives in a small module (e.g., `macllm/core/context.py`) that tools import. All existing tool code that calls `MacLLM._instance.chat_history` or `MacLLM.get_status_manager()` is updated to call `get_current_conversation()` instead.

The agent thread entry point sets the context once at the top:

```python
def run_agent(conversation):
    set_current_conversation(conversation)
    # ... run agent loop ...
```

Tools are completely unaware of this mechanism.

## User Input Model

### Queued queries (new)

Today, pressing Enter while an agent is running aborts the agent. The new model:

- Each conversation has a **query queue**. When the user submits text while an agent is running in that tab, the query is enqueued.
- When the agent finishes its current run, the `run_agent` finally block checks the queue and starts the next query automatically.
- The user sees their queued message appear in the conversation immediately (as a user message), giving visual confirmation.

### Interrupt (explicit)

Aborting an agent becomes an explicit gesture (e.g., Escape key or a dedicated button), not the default behavior of Enter.

- Interrupt aborts the current run (same mechanism as today: `agent.interrupt_switch = True`), generates a summary, then processes any queued queries.
- If the user wants to interrupt and replace, they press the interrupt key and then type a new query.

### Cross-tab behavior

- Submitting in a tab with no running agent starts immediately.
- Submitting in a tab with a running agent enqueues.
- Submitting in a different tab than the one running an agent always starts immediately in that tab's own agent thread.

## Approval Flow

### Mechanism

`pending_approval` is a transient field on `Conversation`. It is not persisted, not part of `messages` or `memory.steps`.

The flow:

1. A tool (e.g., `run_command`) decides it needs approval.
2. The tool sets `conversation.pending_approval = PendingApproval(...)` and calls `request_update()`.
3. The tool blocks on `pending_approval.event.wait()`.
4. The UI renders the conversation. It sees `pending_approval` is set and renders the approval widget as the last item in the view.
5. The user presses a key (R/D/A/H). The UI sets `pending_approval.decision`, calls `pending_approval.event.set()`, and sets `conversation.pending_approval = None`.
6. The tool unblocks, reads the decision, and continues.

### Background tab with pending approval

If the user is viewing a different tab when approval is requested, the agent thread blocks silently. The tab bar shows a visual indicator (e.g., a warning badge) on tabs with pending approvals. When the user switches to that tab, the approval widget renders and the user can act on it.

### Save/reload with pending approval

If the app saves or quits while approval is pending:

- `pending_approval` is not persisted (transient field).
- The agent thread is a daemon thread and dies on app quit.
- The in-progress `ActionStep` has not been finalized by smolagents yet, so it is not in `memory.steps`.
- On reload, the conversation is in a consistent state with the last completed exchange. The interrupted run is simply lost. The user can re-submit if needed.

## Tab Switching

### Unlocked switching

The `is_agent_running()` guards are removed from `switch_to_conversation`, `cycle_conversation`, and `new_conversation`. The user can switch tabs freely regardless of agent state.

The guard remains on `delete_conversation`: a conversation with a running agent cannot be deleted. The user must abort or wait first.

### What happens on switch

When switching tabs, the UI simply changes `conversation_history.active_index` and `MacLLM.chat_history`. The background agent thread for the previous tab continues running. On the next `update_window()`, the UI renders the new active conversation's messages, steps, and approval state.

## UI Rendering Model

### Conversation as sole data source

`update_window()` and `MainTextHandler.set_text_content()` render entirely from conversation state:

- `conversation.messages` for user/assistant text
- `conversation.agent.memory.steps` for tool call progress (while agent is running)
- `conversation.pending_approval` for the approval widget
- `conversation.llm_metadata` for token counts in the top bar

### Tab bar indicators

The tab bar iterates all conversations to render:

- Active tab highlight (as today)
- Running indicator on tabs where `conversation.is_agent_running()` is true
- Approval-needed indicator on tabs where `conversation.pending_approval is not None`

### Title generation as UI concern

Title generation moves out of the agent runtime. The UI notices when a conversation transitions from "New Agent" to having a first completed exchange, and spawns a lightweight background thread to generate the title. The agent is completely unaware of title generation.

## Signal Path: Agent to UI

Every conversation's runtime signals the UI through one path:

1. Something changes on the conversation (new message, step completed, approval requested, tokens updated).
2. The conversation calls its `ui_update_callback`.
3. This calls `ui.request_update()`.
4. `request_update()` posts to the Cocoa main thread with `waitUntilDone_: False` (non-blocking).
5. `update_window()` runs on the main thread and re-reads all state from the active conversation.

Properties:

- **Conversations don't know about the UI.** They fire a generic callback.
- **The UI doesn't know which conversation triggered the update.** It re-reads everything.
- **Agent threads never block on the UI.** The only blocking point is `pending_approval.event.wait()`, which is waiting for user input, not UI rendering.
- **If the UI thread freezes, agents continue running.** Status update messages queue silently in the Cocoa run loop.

## Thread Safety

### Per-conversation isolation

Each conversation's agent thread only writes to its own `Conversation` object. Two agent threads never write to the same conversation (a conversation can only have one agent thread at a time).

### Main thread reads

The main thread reads conversation state for display. This is safe without locks because:

- Python's GIL ensures list/dict mutations are atomic at the bytecode level.
- The UI performs display-only reads (no read-modify-write on conversation data).
- `messages.append()` and `memory.steps` mutations are atomic from the GIL's perspective.

### Persistence lock

`save_all_conversations` is called from both agent threads (on completion) and the main thread (on tab switch). A `threading.Lock` on the save path prevents concurrent disk writes. Contention is minimal (milliseconds of file I/O).

### ConversationHistory mutations

`conversations` list mutations (add, remove, reorder) only happen on the main thread in response to user actions. No lock needed.

## Migration Checklist

### Files to change


| File                           | Change                                                                                                                                                                                                               |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `macllm/core/chat_history.py`  | Add `agent_thread`, `abort_event`, `llm_metadata`, `pending_approval`, `is_agent_running()`, `query_queue`, and `submit()` to `Conversation`. `submit()` handles tag expansion, agent creation, and thread spawning. |
| `macllm/core/context.py`       | New file: thread-local conversation context (`set_current_conversation`, `get_current_conversation`)                                                                                                                 |
| `macllm/macllm.py`             | Remove `_agent_thread`, `_abort_event`, `status_manager`, `llm_metadata`, and `handle_instructions()`. `MacLLM` becomes a bootstrap and global resource holder. Move `/reload` to a tag plugin. Move title generation to the UI. |
| `macllm/core/agent_service.py` | Simplify `create_step_callback` to only handle token accounting and `request_update()`. Remove plan extraction.                                                                                                      |
| `macllm/core/agent_status.py`  | Remove `AgentStatusManager` and `ToolCallEntry`. Keep `PendingApproval` (used by `Conversation.pending_approval`).                                                                                                   |
| `macllm/tools/shell.py`        | Use `get_current_conversation()` from context module. Set `conversation.pending_approval` instead of `status_manager.request_approval()`. Remove `_status_manager()` calls.                                          |
| `macllm/tools/*.py`            | Remove all `_status_manager()` helpers and `start_tool_call` / `complete_tool_call` / `fail_tool_call` calls. Tools just do their work and return.                                                                   |
| `macllm/agents/base.py`        | Remove `MacLLM.get_status_manager()` calls for managed-agent enter/exit.                                                                                                                                             |
| `macllm/ui/core.py`            | Remove `is_agent_running()` guards from tab switching. `handle_user_input` calls `conversation.submit()` directly instead of going through `MacLLM`. Remove `set_status_indicator`. Add explicit interrupt gesture (Escape). |
| `macllm/ui/main_text.py`       | Render tool progress from `agent.memory.steps` instead of `AgentStatusManager`. Render approval from `conversation.pending_approval`. Remove plan rendering.                                                         |
| `macllm/ui/tab_bar.py`         | Add running/approval indicators on tabs.                                                                                                                                                                             |
| `macllm/ui/approval.py`        | Update to read from `conversation.pending_approval` instead of `AgentStatusManager`.                                                                                                                                 |


### Files to remove or gut


| File                          | Action                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------- |
| `macllm/core/agent_status.py` | Remove `AgentStatusManager`, `ToolCallEntry`. Keep `PendingApproval` dataclass. |


