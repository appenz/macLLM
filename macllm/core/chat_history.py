from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field

from macllm.core.user_interaction import PendingApproval, PendingUserInput
from macllm.core.context import get_current_conversation
from macllm.core.virtual_filesystem import create_conversation_root
from macllm.core.conversation_log import (
    ConversationLog,
    append_activity_marker,
    append_plan,
    append_run_end,
    append_run_start,
    add_tool_call as log_add_tool_call,
    clear_activity_markers,
    clear_tool_calls as log_clear_tool_calls,
    complete_last_tool_call as log_complete_last_tool_call,
    message,
    messages_from_log,
    pop_last_tool_call as log_pop_last_tool_call,
    record_last_tool_result as log_record_last_tool_result,
    update_last_tool_message as log_update_last_tool_message,
)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def reset(self):
        self.input_tokens = 0
        self.output_tokens = 0


class Conversation:
    def __init__(self):
        self.conv_id: str = str(uuid.uuid4())
        self.agent = None
        self.current_agent = None
        self.agent_cls = None
        self.ui_update_callback = None
        self.title = "New Agent"

        # Per-conversation agent runtime state (transient, not persisted)
        self.agent_thread: threading.Thread | None = None
        self.abort_event: threading.Event = threading.Event()
        self.usage: Usage = Usage()
        self.pending_approval: PendingApproval | None = None
        self.pending_user_input: PendingUserInput | None = None
        self.pending_input: str = ""
        self.saved_input_text: str = ""
        self._run_step_offset: int = 0
        self._active_query_text: str | None = None
        self._active_run_started_monotonic: float | None = None
        self._user_situation: str | None = None

        self.reset()

    # ------------------------------------------------------------------
    # Live run activity (transient, not persisted)
    # ------------------------------------------------------------------

    def add_activity_marker(self, kind: str, agent_name: str) -> None:
        append_activity_marker(self.conversation_log, kind, agent_name)
        self._notify_ui()

    def clear_run_activity(self) -> None:
        clear_activity_markers(self.conversation_log)
        log_clear_tool_calls(self.conversation_log)

    def add_tool_call(self, tool_name: str, message: str) -> None:
        """Append a live tool-call entry and repaint the UI."""
        log_add_tool_call(self.conversation_log, tool_name, message)
        self._notify_ui()

    def update_last_tool_message(self, message: str) -> None:
        """Override the message of the most recent tool-call entry."""
        log_update_last_tool_message(self.conversation_log, message)
        self._notify_ui()

    def complete_last_tool_call(self, *, failed: bool = False) -> None:
        """Compatibility hook for tools that finish a live tool-call entry."""
        log_complete_last_tool_call(self.conversation_log, failed=failed)
        self._notify_ui()

    def record_last_tool_result(self, tool_name: str, result) -> None:
        """Compatibility hook for tools; observations are stored on ActionStep."""
        log_record_last_tool_result(self.conversation_log, tool_name, result)

    def pop_last_tool_call(self) -> None:
        log_pop_last_tool_call(self.conversation_log)
        self._notify_ui()

    def clear_tool_calls(self) -> None:
        """Reset the live tool-call list (e.g. after a step completes)."""
        log_clear_tool_calls(self.conversation_log)

    def is_agent_running(self) -> bool:
        return self.agent_thread is not None and self.agent_thread.is_alive()

    # ------------------------------------------------------------------
    # submit() — the main entry point for user queries
    # ------------------------------------------------------------------

    def submit(self, user_input: str) -> None:
        """Submit a user query to this conversation.

        If the agent is already running the text is accumulated into
        ``pending_input`` (joined with newlines when multiple submissions
        arrive) and will be processed as a single query after the current
        run finishes.  Otherwise processing starts immediately.
        """
        user_input = user_input.strip()
        if not user_input:
            return

        if self.pending_user_input is not None:
            self.add_user_message(user_input)
            self.resolve_user_input(user_input)
            self._notify_ui()
            return

        if self.is_agent_running():
            if self.pending_input:
                self.pending_input += "\n" + user_input
            else:
                self.pending_input = user_input
            self._notify_ui()
            return

        self._process_query(user_input)

    def _process_query(self, user_input: str) -> None:
        """Expand tags, create agent, and spawn the agent thread."""
        from macllm.macllm import MacLLM
        from macllm.core.user_request import UserRequest
        from macllm.core.skills import SkillsRegistry

        app = MacLLM._instance

        try:
            expanded_input = SkillsRegistry.expand_manual_invocation(user_input)

            err = SkillsRegistry.failed_leading_slash_skill_message(
                user_input, expanded_input, app.plugins
            )
            if err:
                self.add_user_message(user_input)
                self.add_assistant_message(err)
                self._notify_ui()
                return

            request = UserRequest(expanded_input)
            if not request.process_tags(app.plugins, self, app.debug_log, app.debug_exception, app._prefix_index):
                app.debug_log(f'submit: {user_input} - Abort on plugin failure', 1)
                return

            self.add_user_message(user_input)

            if self.agent is None and request.agent_name is not None:
                from macllm.agents import get_agent_class
                self.agent_cls = get_agent_class(request.agent_name)
            if self.agent is None and request.speed_level is not None:
                self.speed_level = request.speed_level

            if not request.expanded_prompt.strip():
                self._notify_ui()
                return

            self._reset_run_state()
            self._active_query_text = user_input

            if self.agent is None:
                self._create_agent()

            self._start_agent_thread(request, app)

        except Exception as e:
            app.debug_exception(e)

    def _start_agent_thread(self, request, app) -> None:
        """Spawn the background agent thread for this conversation."""
        from macllm.core.context import set_current_conversation
        from macllm.core.persistence import save_all_conversations
        from macllm.core.llm_service import get_model_for_speed

        conversation = self

        def run_agent():
            set_current_conversation(conversation)
            run_status = "success"
            run_error = None
            try:
                conversation.abort_event.clear()
                conversation.clear_run_activity()
                from macllm.tools.web_search import reset_search_counter
                from smolagents import PlanningStep

                reset_search_counter()
                conversation.agent.memory.steps = [
                    s
                    for s in conversation.agent.memory.steps
                    if not isinstance(s, PlanningStep)
                ]
                conversation._run_step_offset = len(conversation.agent.memory.steps)

                max_steps = 1 if request.no_tools else 10
                run_kwargs = dict(max_steps=max_steps, reset=False)
                conversation._active_run_started_monotonic = time.monotonic()
                agent_cls = conversation._get_agent_cls()
                append_run_start(conversation.conversation_log, {
                    "query": conversation._active_query_text,
                    "expanded_prompt": request.expanded_prompt,
                    "agent": getattr(agent_cls, "macllm_name", None),
                    "speed": conversation.speed_level,
                    "model": get_model_for_speed(conversation.speed_level),
                    "max_steps": max_steps,
                    "no_tools": bool(request.no_tools),
                })

                conversation.agent._tools_disabled = bool(request.no_tools)
                conversation.current_agent = conversation.agent
                result = conversation.agent.run(request.expanded_prompt, **run_kwargs)

                if isinstance(result, str):
                    result = result.strip()

                if result:
                    conversation.add_assistant_message(result)
                else:
                    conversation.add_assistant_message("Error: No output from agent")

                conversation._maybe_generate_title()
            except Exception as e:
                if conversation.abort_event.is_set():
                    run_status = "aborted"
                    conversation._handle_abort(app)
                else:
                    run_status = "error"
                    run_error = str(e)
                    app.debug_exception(e)
                    conversation.add_assistant_message(f"Error: {str(e)}")
            finally:
                conversation.current_agent = None
                conversation.agent._tools_disabled = False
                started = conversation._active_run_started_monotonic
                append_run_end(conversation.conversation_log, {
                    "status": run_status,
                    "error": run_error,
                    "elapsed_seconds": (
                        time.monotonic() - started
                        if started is not None else None
                    ),
                    "input_tokens": conversation.usage.input_tokens,
                    "output_tokens": conversation.usage.output_tokens,
                    "total_tokens": (
                        conversation.usage.input_tokens
                        + conversation.usage.output_tokens
                    ),
                })
                conversation.clear_run_activity()
                conversation._active_run_started_monotonic = None
                if not app.ephemeral:
                    save_all_conversations(app.conversation_history)
                conversation.agent_thread = None
                conversation.abort_event.clear()
                conversation._notify_ui()
                if getattr(app.args, 'query', None):
                    screenshot_path = getattr(app.args, 'screenshot', None)
                    app.ui.schedule_quit(screenshot_path=screenshot_path)
                conversation._drain_pending_input()

        self.agent_thread = threading.Thread(target=run_agent, daemon=True)
        self.agent_thread.start()
        self._notify_ui()

    def _drain_pending_input(self) -> None:
        """Submit accumulated pending input as a single query, if any."""
        text = self.pending_input
        self.pending_input = ""
        if text:
            self._process_query(text)

    def abort(self) -> None:
        """Signal the running agent to abort.

        Adds an immediate "Interrupted." assistant message so the user
        sees visual feedback right away (before the agent thread exits).
        """
        if not self.is_agent_running():
            return
        self.add_assistant_message("Interrupted.")
        self.abort_event.set()
        if self.pending_approval is not None:
            self.resolve_approval("deny")
        if self.pending_user_input is not None:
            self.cancel_user_input()
        if self.agent:
            self.agent.interrupt_switch = True
            for agent in getattr(self.agent, 'managed_agents', {}).values():
                agent.interrupt_switch = True
        self.clear_run_activity()
        self._notify_ui()

    def resolve_approval(self, decision: str) -> None:
        """Resolve the current pending approval with the user's decision."""
        if self.pending_approval is not None:
            self.pending_approval.decision = decision
            self.pending_approval.event.set()
            self.pending_approval = None
            self._notify_ui()

    def request_user_input(self, question: str) -> str:
        """Ask a question in chat and wait for the next normal user input."""
        pending = PendingUserInput(question=question.strip())
        self.pending_user_input = pending
        self.add_assistant_message(pending.question)
        self._notify_ui()

        pending.event.wait()
        try:
            if pending.cancelled:
                return "User input request was cancelled."
            return pending.response or ""
        finally:
            if self.pending_user_input is pending:
                self.pending_user_input = None
            self._notify_ui()

    def resolve_user_input(self, response: str) -> None:
        """Resolve a pending user-input tool call with normal chat text."""
        if self.pending_user_input is not None:
            self.pending_user_input.response = response
            self.pending_user_input.event.set()

    def cancel_user_input(self) -> None:
        """Cancel a pending user-input request without blocking the agent thread."""
        if self.pending_user_input is not None:
            self.pending_user_input.cancelled = True
            self.pending_user_input.event.set()

    def _handle_abort(self, app) -> None:
        """After an abort, persist state without adding any message."""
        if not app.ephemeral:
            from macllm.core.persistence import save_all_conversations
            save_all_conversations(app.conversation_history)

    def _maybe_generate_title(self) -> None:
        """Generate a short title after the first exchange."""
        if self.title != "New Agent":
            return
        messages = messages_from_log(self.conversation_log)
        user_msgs = [m for m in messages if m["role"] == "user"]
        asst_msgs = [m for m in messages if m["role"] == "assistant"]
        if len(user_msgs) != 1 or len(asst_msgs) != 1:
            return
        try:
            from macllm.macllm import MacLLM
            from macllm.core.llm_service import generate
            from macllm.core.persistence import save_all_conversations
            app = MacLLM._instance
            user_text = user_msgs[0]["content"][:200]
            asst_text = asst_msgs[0]["content"][:200]
            prompt = (
                "Generate a 2-3 word title for this conversation. "
                "Reply with ONLY the title, nothing else.\n\n"
                f"User: {user_text}\n"
                f"Assistant: {asst_text}"
            )
            speed = getattr(self, 'speed_level', 'normal') or 'normal'
            title_text, _ = generate(
                messages=[{"role": "user", "content": prompt}],
                speed=speed,
            )
            title = title_text.strip().strip('"').strip("'")
            if title:
                self.title = title[:30]
                if app and not app.ephemeral:
                    save_all_conversations(app.conversation_history)
                self._notify_ui()
        except Exception:
            pass

    def _notify_ui(self) -> None:
        if self.ui_update_callback:
            self.ui_update_callback()

    def _reset_run_state(self) -> None:
        """Reset transient per-run UI state before starting an agent run."""
        self.usage.reset()
        self.clear_run_activity()

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """Add a user message (display text only)."""
        self.conversation_log.append(message("user", content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        self.conversation_log.append(message("assistant", content))

    def add_system_message(self, content: str) -> None:
        """Add or update system message (typically only at conversation start)."""
        self.conversation_log.append(message("system", content))

    def add_source(self, kind: str, ref: str) -> None:
        """Record that a tool directly read an external item on this conversation.

        Dedupes by ``(kind, ref)`` and moves a repeat read to the end (newest).
        Callers pass canonical refs; this method does not normalize.
        Prefer the module-level ``add_source`` from tools so conversation
        lookup stays in one place.
        """
        self.sources = [
            s for s in self.sources
            if not (s.get("kind") == kind and s.get("ref") == ref)
        ]
        self.sources.append({"kind": kind, "ref": ref})
        self._notify_ui()

    def queue_observation_images(self, images: list) -> None:
        """Stash images from a tool result for the next ActionStep callback."""
        if not images:
            return
        self._pending_observation_images.extend(images)

    def take_observation_images(self) -> list:
        """Return and clear pending observation images."""
        images = list(self._pending_observation_images)
        self._pending_observation_images = []
        return images

    def has_path_in_context(self, path: str) -> bool:
        """Check if a file path appears in Sources or granted directories."""
        abs_path = os.path.abspath(os.path.expanduser(path))
        for src in self.sources:
            if src.get("kind") == "file" and src.get("ref") == abs_path:
                return True
        for granted in self.get_granted_dirs():
            root = os.path.abspath(granted)
            if abs_path == root or abs_path.startswith(root + os.sep):
                return True
        return False

    def _get_agent_cls(self):
        if self.agent_cls is None:
            from macllm.agents import get_default_agent_class
            self.agent_cls = get_default_agent_class()
        return self.agent_cls

    def get_user_situation(self) -> str:
        if self._user_situation is None:
            from macllm.core.device_context import get_device_context
            self._user_situation = get_device_context()
        return self._user_situation

    def grant_directory(self, path: str) -> None:
        """Add a directory to the sandbox grant list for this conversation."""
        abs_path = os.path.abspath(os.path.expanduser(path))
        if abs_path not in self.granted_dirs:
            self.granted_dirs.append(abs_path)

    def get_granted_dirs(self) -> list[str]:
        """Return all granted directories (config defaults + conversation grants)."""
        from macllm.core.config import get_runtime_config
        config = get_runtime_config()
        config_dirs = [
            os.path.abspath(os.path.expanduser(d))
            for d in config.shell.default_dirs
        ]
        return list(dict.fromkeys(config_dirs + self.granted_dirs))

    def reset(self, clear_persisted: bool = False) -> None:
        """Clears messages and metadata, restores default welcome message."""
        self.conversation_log = ConversationLog()
        self.sources: list[dict] = []
        self._pending_observation_images: list = []
        self.granted_dirs: list[str] = []
        self.speed_level = "normal"
        self.title = "New Agent"
        self.pending_user_input = None
        self._active_query_text = None
        self._user_situation = None

        self._get_agent_cls()

        if self.agent is not None:
            self.agent.memory.steps = []
            self.agent = None

        if clear_persisted:
            from macllm.core.persistence import clear_conversation
            clear_conversation()

    def _create_agent(self):
        """Create agent instance using the current agent class."""
        from macllm.core.agent_service import create_agent

        self.agent = create_agent(
            agent_cls=self._get_agent_cls(),
            speed=self.speed_level,
            conversation=self,
        )


class ConversationHistory:
    def __init__(self):
        self.conversations = []
        self.active_index = -1

    def add_conversation(self, conversation=None):
        """Add a new Conversation object and make it the current (active) conversation."""
        from macllm.core.context import register_conversation

        if conversation is None:
            conversation = Conversation()
        create_conversation_root(conversation)
        register_conversation(conversation)
        self.conversations.append(conversation)
        self.active_index = len(self.conversations) - 1
        return conversation

    def get_current_conversation(self):
        """Return the active Conversation object, or None if none exists."""
        if self.conversations and 0 <= self.active_index < len(self.conversations):
            return self.conversations[self.active_index]
        return None

    def set_active(self, index: int) -> bool:
        """Switch the active conversation by index. Returns True on success."""
        if 0 <= index < len(self.conversations):
            self.active_index = index
            return True
        return False

    def cycle(self, delta: int) -> bool:
        """Move active index by delta (clamped to bounds). Returns True if changed."""
        if not self.conversations:
            return False
        new_index = max(0, min(len(self.conversations) - 1, self.active_index + delta))
        if new_index == self.active_index:
            return False
        self.active_index = new_index
        return True

    def remove_conversation(self, index: int) -> bool:
        """Remove conversation at *index*, ensuring at least one always exists."""
        from macllm.core.context import unregister_conversation

        if index < 0 or index >= len(self.conversations):
            return False
        unregister_conversation(self.conversations[index])
        self.conversations.pop(index)
        if not self.conversations:
            self.add_conversation()
            return True
        if index < self.active_index:
            self.active_index -= 1
        elif index == self.active_index:
            self.active_index = min(self.active_index, len(self.conversations) - 1)
        return True


def add_source(kind: str, ref: str) -> None:
    """Record a direct tool read on the current conversation, if any."""
    conv = get_current_conversation()
    if conv is not None:
        conv.add_source(kind, ref)
