# Agent Status Display

During agent execution, macLLM displays real-time status information to the user. This document describes the two-section status display and the `AgentStatusManager` API.

## Display Format

The status display shows two sections at the bottom of the conversation during agent execution:

```
Plan
  1. Search for relevant information
  2. Analyze the results
  3. Provide a summary

Steps
  ✓ web_search("python async")
  ✓ web_search("asyncio best practices")
  ⟳ file_append("/tmp/notes.txt")
  ✗ web_search("invalid query") — API rate limit exceeded
```

### Section Details

**Plan**: The current execution plan from the agent's planning step. Updated when the agent replans.

**Steps**: Log of all tool invocations with status indicators:
- `⟳` - Running (tool execution in progress)
- `✓` - Success (tool completed successfully)
- `✗` - Error (tool failed, shows error summary)

## AgentStatusManager API

Located in `macllm/core/agent_status.py`.

### ToolCallEntry

```python
@dataclass
class ToolCallEntry:
    id: str                    # Unique identifier for this call
    name: str                  # Tool name (e.g., "web_search")
    args_summary: str          # Short summary of arguments
    status: Literal["running", "success", "error"]
    result_summary: str = ""   # Brief result or error message
    started_at: float          # Timestamp from time.time()
```

### AgentStatusManager

```python
class AgentStatusManager:
    plan: str                      # Current plan text
    tool_calls: list[ToolCallEntry]
    ui_update_callback: Callable   # Called after any update
    
    def set_plan(self, plan: str) -> None
    def start_tool_call(self, id: str, name: str, args: dict) -> None
    def complete_tool_call(self, id: str, result: str = "") -> None
    def fail_tool_call(self, id: str, error: str) -> None
    def reset(self) -> None        # Clear all state for new agent run
    def render(self) -> str        # Format all sections for display
```

All mutating methods trigger `ui_update_callback()` after updating state.

## Integration

### Accessing the Status Manager

The `AgentStatusManager` is stored in the `MacLLM` singleton and accessed via:

```python
from macllm.macllm import MacLLM

MacLLM.get_status_manager().complete_tool_call(tool_id, result)
```

### Step Callbacks (agent_service.py)

The step callback in `create_step_callback()` handles:

- **PlanningStep**: Calls `set_plan()` with extracted content
- **ActionStep**: Calls `start_tool_call()` for each tool in `step.tool_calls`

### Tools

All tools report their own status via the status manager:

**Long-running tools** (e.g., `web_search`, `search_files`) call `start_tool_call()` at the beginning and `complete_tool_call()`/`fail_tool_call()` at the end:

```python
@tool
def web_search(queries: list[str]) -> str:
    tool_id = f"web_search_{counter}_{int(time.time() * 1000)}"
    status = MacLLM.get_status_manager()
    status.start_tool_call(tool_id, "web_search", {"queries": queries})
    
    try:
        # ... do work ...
        status.complete_tool_call(tool_id, f"{len(queries)} queries done")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise
```

**Instant tools** (e.g., `get_current_time`) only call `complete_tool_call()` at the end (no visible "running" state since they're instantaneous):

```python
@tool
def get_current_time() -> str:
    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    tool_id = f"get_current_time_{counter}_{int(time.time() * 1000)}"
    MacLLM.get_status_manager().complete_tool_call(tool_id, result)
    
    return result
```

The status manager handles both patterns - if `complete_tool_call()` is called without a prior `start_tool_call()`, it creates the entry directly as "success".

## Data Flow

```
smolagents step callback
    │
    ├─► PlanningStep ─► set_plan()
    │
    └─► ActionStep ─► start_tool_call() for each tool
                          │
                          ▼
                    Tool executes
                          │
                          ├─► complete_tool_call() (from tool or next step)
                          │
                          └─► fail_tool_call() (on error)
                                  │
                                  ▼
                          ui_update_callback()
                                  │
                                  ▼
                          MainTextHandler renders status_manager.render()
```
