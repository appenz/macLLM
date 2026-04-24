from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from typing import List, Dict, Optional, Union

from macllm.core.agent_status import PendingApproval


class Conversation:
    def __init__(self):
        self.conv_id: str = str(uuid.uuid4())
        self.agent = None
        self.agent_cls = None
        self.ui_update_callback = None
        self.title = "New Agent"

        # Per-conversation agent runtime state (transient, not persisted)
        self.agent_thread: threading.Thread | None = None
        self.abort_event: threading.Event = threading.Event()
        self.llm_metadata: dict = {'input_tokens': 0, 'output_tokens': 0}
        self.pending_approval: PendingApproval | None = None
        self.query_queue: list = []
        self.saved_input_text: str = ""
        self._run_step_offset: int = 0

        self.reset()

    # ------------------------------------------------------------------
    # Live tool-call tracking (transient, not persisted)
    # ------------------------------------------------------------------

    tool_calls: list

    def add_tool_call(self, tool_name: str, message: str) -> None:
        """Append a live tool-call entry and repaint the UI."""
        self.tool_calls.append({"tool": tool_name, "message": message})
        self._notify_ui()

    def update_last_tool_message(self, message: str) -> None:
        """Override the message of the most recent tool-call entry."""
        if self.tool_calls:
            self.tool_calls[-1]["message"] = message
            self._notify_ui()

    def pop_last_tool_call(self) -> None:
        if self.tool_calls:
            self.tool_calls.pop()
            self._notify_ui()

    def clear_tool_calls(self) -> None:
        """Reset the live tool-call list (e.g. after a step completes)."""
        self.tool_calls.clear()

    def is_agent_running(self) -> bool:
        return self.agent_thread is not None and self.agent_thread.is_alive()

    # ------------------------------------------------------------------
    # submit() — the main entry point for user queries
    # ------------------------------------------------------------------

    def submit(self, user_input: str) -> None:
        """Submit a user query to this conversation.

        If the agent is already running the query is enqueued and will be
        processed after the current run finishes.  Otherwise processing
        starts immediately on a new background thread.
        """
        user_input = user_input.strip()
        if not user_input:
            return

        if self.is_agent_running():
            self.query_queue.append(user_input)
            self.add_user_message(user_input)
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

            if request.agent_name is not None:
                from macllm.agents import get_agent_class
                self.agent_cls = get_agent_class(request.agent_name)
            if request.speed_level is not None:
                self.speed_level = request.speed_level

            if not request.expanded_prompt.strip():
                self._notify_ui()
                return

            self.llm_metadata['input_tokens'] = 0
            self.llm_metadata['output_tokens'] = 0

            def token_callback(input_tokens: int, output_tokens: int):
                self.llm_metadata['input_tokens'] = input_tokens
                self.llm_metadata['output_tokens'] = output_tokens
                self._notify_ui()

            self._create_agent(token_callback=token_callback)

            self._start_agent_thread(request, app)

        except Exception as e:
            app.debug_exception(e)

    def _start_agent_thread(self, request, app) -> None:
        """Spawn the background agent thread for this conversation."""
        from macllm.core.context import set_current_conversation
        from macllm.core.memory import save_all_conversations
        from macllm.core.llm_service import model_supports_vision

        conversation = self

        def run_agent():
            set_current_conversation(conversation)
            try:
                conversation.abort_event.clear()
                conversation.clear_tool_calls()
                conversation._run_step_offset = len(conversation.agent.memory.steps)

                # #region agent log
                try:
                    payload = {
                        "sessionId": "db8a81",
                        "runId": "ctrl-c-stack-probe",
                        "hypothesisId": "H1,H3,H4",
                        "location": "macllm/core/chat_history.py:run_agent:start",
                        "message": "Agent thread started for conversation",
                        "data": {
                            "conv_id": conversation.conv_id,
                            "thread_ident": threading.get_ident(),
                            "agent_thread_ident": conversation.agent_thread.ident if conversation.agent_thread else None,
                            "is_agent_running": conversation.is_agent_running(),
                            "active_index": getattr(app.conversation_history, "active_index", None),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                    with open("/Users/gappenzeller/dev/myprojects/macLLM/.cursor/debug-db8a81.log", "a", encoding="utf-8") as log_file:
                        log_file.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
                # #endregion

                run_kwargs = dict(max_steps=10, reset=False)
                if request.images:
                    if model_supports_vision(conversation.speed_level):
                        run_kwargs["images"] = request.images
                    else:
                        app.debug_log("Current model does not support images; ignoring attached images", 1)

                result = conversation.agent.run(request.expanded_prompt, **run_kwargs)

                if isinstance(result, str):
                    result = result.strip()

                if result:
                    conversation.add_assistant_message(result)
                else:
                    conversation.add_assistant_message("Error: No output from agent")

                if not app.ephemeral:
                    save_all_conversations(app.conversation_history)

                conversation._maybe_generate_title()

                app.debug_log(f'Output: {result}\n')
            except Exception as e:
                if conversation.abort_event.is_set():
                    conversation._handle_abort_summary(request.expanded_prompt, app)
                else:
                    app.debug_exception(e)
                    conversation.add_assistant_message(f"Error: {str(e)}")
                    if not app.ephemeral:
                        save_all_conversations(app.conversation_history)
            finally:
                # #region agent log
                try:
                    payload = {
                        "sessionId": "db8a81",
                        "runId": "ctrl-c-stack-probe",
                        "hypothesisId": "H1,H2,H5",
                        "location": "macllm/core/chat_history.py:run_agent:finally",
                        "message": "Agent thread exiting for conversation",
                        "data": {
                            "conv_id": conversation.conv_id,
                            "thread_ident": threading.get_ident(),
                            "abort_event_set": conversation.abort_event.is_set(),
                            "queue_length": len(conversation.query_queue),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                    with open("/Users/gappenzeller/dev/myprojects/macLLM/.cursor/debug-db8a81.log", "a", encoding="utf-8") as log_file:
                        log_file.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
                # #endregion
                conversation.agent_thread = None
                conversation.abort_event.clear()
                conversation._notify_ui()
                if getattr(app.args, 'query', None):
                    screenshot_path = getattr(app.args, 'screenshot', None)
                    app.ui.schedule_quit(screenshot_path=screenshot_path)
                conversation._drain_queue()

        self.agent_thread = threading.Thread(target=run_agent, daemon=True)
        self.agent_thread.start()

    def _drain_queue(self) -> None:
        """Process the next queued query, if any."""
        if self.query_queue:
            next_query = self.query_queue.pop(0)
            self._process_query(next_query)

    def abort(self) -> None:
        """Signal the running agent to abort."""
        if not self.is_agent_running():
            return
        self.abort_event.set()
        if self.pending_approval is not None:
            self.resolve_approval("deny")
        if self.agent:
            self.agent.interrupt_switch = True
            for agent in getattr(self.agent, 'managed_agents', {}).values():
                agent.interrupt_switch = True

    def resolve_approval(self, decision: str) -> None:
        """Resolve the current pending approval with the user's decision."""
        if self.pending_approval is not None:
            self.pending_approval.decision = decision
            self.pending_approval.event.set()
            self.pending_approval = None
            self._notify_ui()

    def _handle_abort_summary(self, task, app) -> None:
        """After an abort, record a static interrupted message (no LLM call)."""
        self.add_assistant_message("Interrupted.")
        if not app.ephemeral:
            from macllm.core.memory import save_all_conversations
            save_all_conversations(app.conversation_history)

    def _maybe_generate_title(self) -> None:
        """Generate a short title after the first exchange."""
        if self.title != "New Agent":
            return
        user_msgs = [m for m in self.messages if m["role"] == "user"]
        asst_msgs = [m for m in self.messages if m["role"] == "assistant"]
        if len(user_msgs) != 1 or len(asst_msgs) != 1:
            return
        try:
            from macllm.macllm import MacLLM
            from macllm.core.llm_service import generate
            from macllm.core.memory import save_all_conversations
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

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """Add a user message (display text only)."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        self.messages.append({"role": "assistant", "content": content})

    def add_system_message(self, content: str) -> None:
        """Add or update system message (typically only at conversation start)."""
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = content
        else:
            self.messages.insert(0, {"role": "system", "content": content})

    def get_displayable_messages(self) -> List[Dict]:
        """Returns messages for UI rendering (user and assistant only)."""
        return [
            m for m in self.messages
            if m["role"] in ("user", "assistant")
        ]

    def add_context(self, suggested_name: str, source: str, context_type: str, context: Union[str, bytes], icon=None) -> str:
        """Add context entry, returns the actual name used. Avoids duplicates based on source."""
        for ctx in self.context_history:
            if ctx['source'] == source:
                return ctx['name']

        actual_name = suggested_name
        counter = 1
        while any(ctx['name'] == actual_name for ctx in self.context_history):
            actual_name = f"{suggested_name}-{counter}"
            counter += 1

        if icon is None:
            icon = ""

        entry = {
            'name': actual_name,
            'source': source,
            'type': context_type,
            'context': context,
            'icon': icon
        }
        self.context_history.append(entry)
        return actual_name

    def has_path_in_context(self, path: str) -> bool:
        """Check if a file path was explicitly referenced in this conversation's context."""
        for ctx in self.context_history:
            if ctx.get("type") == "path" and ctx.get("source") == path:
                return True
        return False

    def _get_agent_cls(self):
        if self.agent_cls is None:
            from macllm.agents import get_default_agent_class
            self.agent_cls = get_default_agent_class()
        return self.agent_cls

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
        self.messages = []
        self.context_history = []
        self.granted_dirs: list[str] = []
        self.speed_level = "normal"
        self.title = "New Agent"
        self.tool_calls = []

        self._get_agent_cls()

        if self.agent is not None:
            self.agent.memory.steps = []
            self.agent = None

        if clear_persisted:
            from macllm.core.memory import clear_conversation
            clear_conversation()

    def _create_agent(self, token_callback=None):
        """Create agent instance using the current agent class."""
        from macllm.core.agent_service import create_agent

        old_steps = None
        if self.agent is not None:
            old_steps = self.agent.memory.steps

        self.agent = create_agent(
            agent_cls=self._get_agent_cls(),
            speed=self.speed_level,
            token_callback=token_callback,
        )

        if old_steps is not None:
            self.agent.memory.steps = old_steps


class ConversationHistory:
    def __init__(self):
        self.conversations = []
        self.active_index = -1

    def add_conversation(self, conversation=None):
        """Add a new Conversation object and make it the current (active) conversation."""
        from macllm.core.context import register_conversation

        if conversation is None:
            conversation = Conversation()
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
