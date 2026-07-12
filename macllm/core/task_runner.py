"""Headless task runner for macLLM.

Parses task files (markdown with optional skill-style frontmatter), runs the
agent synchronously without a UI, enforces token/time budgets, and routes
output to stdout or a logfile.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from macllm.core.skills import _FRONTMATTER_RE, _parse_frontmatter
from macllm.core.virtual_filesystem import create_conversation_root


DEFAULT_TOKEN_BUDGET = 100_000
DEFAULT_TIME_BUDGET = 1800  # 30 minutes


@dataclass
class TaskDefinition:
    """Parsed task file: frontmatter properties + body text."""

    body: str
    name: str = ""
    description: str = ""
    token_budget: int = DEFAULT_TOKEN_BUDGET
    time_budget: int = DEFAULT_TIME_BUDGET
    logfile: str | None = None
    source: str = ""


def parse_task_file(path: str) -> TaskDefinition:
    """Read a task file and return a ``TaskDefinition``.

    The file format is identical to skill files: optional ``---`` frontmatter
    block(s) followed by a markdown body.  Task-specific keys (``token-budget``,
    ``time-budget``, ``logfile``) are extracted; skill-only keys are ignored.
    """
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Task file not found: {path}")

    text = p.read_text(encoding="utf-8")
    return parse_task_text(text, source=str(p))


def parse_task_text(text: str, source: str = "<string>") -> TaskDefinition:
    """Parse task content from a string (useful for tests)."""
    matches = list(_FRONTMATTER_RE.finditer(text))

    if not matches:
        return TaskDefinition(body=text.strip(), source=source)

    m0 = matches[0]
    fm = _parse_frontmatter(m0.group(1))

    name = fm.get("name", "").strip()
    description = fm.get("description", "").strip()

    token_budget = DEFAULT_TOKEN_BUDGET
    raw_tb = fm.get("token-budget", "").strip()
    if raw_tb:
        try:
            token_budget = int(raw_tb)
        except ValueError:
            pass

    time_budget = DEFAULT_TIME_BUDGET
    raw_time = fm.get("time-budget", "").strip()
    if raw_time:
        try:
            time_budget = int(raw_time)
        except ValueError:
            pass

    logfile = fm.get("logfile", "").strip() or None

    body = text[m0.end():].strip()

    return TaskDefinition(
        body=body,
        name=name,
        description=description,
        token_budget=token_budget,
        time_budget=time_budget,
        logfile=logfile,
        source=source,
    )


def apply_cli_overrides(task: TaskDefinition, args) -> TaskDefinition:
    """Apply CLI flags on top of task-file values (CLI wins)."""
    if getattr(args, "token_budget", None) is not None:
        task.token_budget = args.token_budget
    if getattr(args, "time_budget", None) is not None:
        task.time_budget = args.time_budget
    if getattr(args, "logfile", None) is not None:
        task.logfile = args.logfile
    return task


class _OutputRouter:
    """Routes output to stdout or a logfile."""

    def __init__(self, logfile: str | None, debug: bool = False):
        self._file = None
        self._debug = debug
        if logfile:
            p = Path(logfile).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(p, "w", encoding="utf-8")

    def write(self, text: str) -> None:
        if self._file:
            self._file.write(text)
            self._file.flush()
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    def debug(self, text: str) -> None:
        if not self._debug:
            return
        if self._file:
            self._file.write(text)
            self._file.flush()
        else:
            sys.stderr.write(text)
            sys.stderr.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None


def run_task(task: TaskDefinition, args) -> int:
    """Execute a task headlessly and return an exit code (0 or 1)."""
    from macllm.core.chat_history import Conversation
    from macllm.core.context import set_current_conversation, register_conversation
    from macllm.core.config import load_runtime_config
    from macllm.core.llm_service import refresh_models
    from macllm.core.skills import SkillsRegistry

    output = _OutputRouter(task.logfile, debug=getattr(args, "debug", False))

    try:
        output.debug(f"[task] Starting task: {task.name or task.source}\n")
        output.debug(f"[task] Token budget: {task.token_budget}, Time budget: {task.time_budget}s\n")

        load_runtime_config()
        refresh_models()
        SkillsRegistry.reload()

        conversation = Conversation()
        create_conversation_root(conversation)
        register_conversation(conversation)
        set_current_conversation(conversation)

        start_time = time.monotonic()

        budget_state = {"exceeded": False, "reason": ""}

        def budget_check(step, agent):
            elapsed = time.monotonic() - start_time
            total_tokens = conversation.usage.input_tokens + conversation.usage.output_tokens

            if total_tokens > task.token_budget:
                budget_state["exceeded"] = True
                budget_state["reason"] = (
                    f"Token budget exceeded ({total_tokens} > {task.token_budget})"
                )
                output.debug(f"[task] {budget_state['reason']}, interrupting agent\n")
                agent.interrupt_switch = True

            if elapsed > task.time_budget:
                budget_state["exceeded"] = True
                budget_state["reason"] = (
                    f"Time budget exceeded ({elapsed:.0f}s > {task.time_budget}s)"
                )
                output.debug(f"[task] {budget_state['reason']}, interrupting agent\n")
                agent.interrupt_switch = True

        from macllm.agents import get_default_agent_class
        agent_cls = get_default_agent_class()
        agent = agent_cls(
            speed=conversation.speed_level,
            conversation=conversation,
            no_tools=False,
            task_mode=True,
        )
        conversation.agent = agent

        from smolagents import PlanningStep, ActionStep
        agent.step_callbacks.register(PlanningStep, budget_check)
        agent.step_callbacks.register(ActionStep, budget_check)

        output.debug(f"[task] Agent created, running task...\n")

        max_steps = _max_steps_for_budget(task.token_budget)

        try:
            result = agent.run(task.body, max_steps=max_steps)
        except Exception as run_err:
            if budget_state["exceeded"]:
                output.debug(f"[task] Agent interrupted by budget, requesting final answer\n")
                try:
                    final_msg = agent.provide_final_answer(task.body)
                    result = getattr(final_msg, "content", None) or str(final_msg)
                except Exception:
                    result = f"[Task interrupted: {budget_state['reason']}]"
            else:
                raise run_err

        if isinstance(result, str):
            result = result.strip()

        if budget_state["exceeded"]:
            output.debug(f"[task] {budget_state['reason']}\n")

        output.write(result + "\n" if result else "")

        elapsed = time.monotonic() - start_time
        total_tokens = conversation.usage.input_tokens + conversation.usage.output_tokens
        output.debug(f"[task] Completed in {elapsed:.1f}s, {total_tokens} tokens\n")

        return 0

    except Exception as e:
        output.debug(f"[task] Error: {e}\n")
        sys.stderr.write(f"Error: {e}\n")
        return 1

    finally:
        output.close()


def _max_steps_for_budget(token_budget: int) -> int:
    """Heuristic: allow more steps for larger token budgets."""
    if token_budget <= 10_000:
        return 5
    if token_budget <= 50_000:
        return 15
    return 30
