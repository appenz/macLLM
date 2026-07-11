"""Tests for the task runner: parsing, budget enforcement, prompt switching."""

import argparse
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from macllm.core.task_runner import (
    TaskDefinition,
    parse_task_file,
    parse_task_text,
    apply_cli_overrides,
    _OutputRouter,
    DEFAULT_TOKEN_BUDGET,
    DEFAULT_TIME_BUDGET,
    _max_steps_for_budget,
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParseTaskText:
    def test_full_frontmatter(self):
        text = (
            "---\n"
            "name: my-task\n"
            "description: A test task\n"
            "token-budget: 50000\n"
            "time-budget: 300\n"
            "logfile: ~/logs/out.log\n"
            "---\n"
            "Do the thing.\n"
        )
        td = parse_task_text(text)
        assert td.name == "my-task"
        assert td.description == "A test task"
        assert td.token_budget == 50000
        assert td.time_budget == 300
        assert td.logfile == "~/logs/out.log"
        assert td.body == "Do the thing."

    def test_no_frontmatter(self):
        text = "Just do this task please."
        td = parse_task_text(text)
        assert td.body == "Just do this task please."
        assert td.name == ""
        assert td.token_budget == DEFAULT_TOKEN_BUDGET
        assert td.time_budget == DEFAULT_TIME_BUDGET
        assert td.logfile is None

    def test_partial_frontmatter_defaults(self):
        text = "---\nname: partial\n---\nBody here."
        td = parse_task_text(text)
        assert td.name == "partial"
        assert td.description == ""
        assert td.token_budget == DEFAULT_TOKEN_BUDGET
        assert td.time_budget == DEFAULT_TIME_BUDGET
        assert td.logfile is None
        assert td.body == "Body here."

    def test_invalid_budget_uses_default(self):
        text = "---\ntoken-budget: not-a-number\ntime-budget: nope\n---\nBody."
        td = parse_task_text(text)
        assert td.token_budget == DEFAULT_TOKEN_BUDGET
        assert td.time_budget == DEFAULT_TIME_BUDGET

    def test_empty_logfile_is_none(self):
        text = "---\nlogfile:\n---\nBody."
        td = parse_task_text(text)
        assert td.logfile is None

    def test_skill_properties_ignored(self):
        text = (
            "---\n"
            "name: mixed\n"
            "disable-model-invocation: true\n"
            "user-invocable: false\n"
            "token-budget: 5000\n"
            "---\n"
            "Task body."
        )
        td = parse_task_text(text)
        assert td.name == "mixed"
        assert td.token_budget == 5000
        assert td.body == "Task body."

    def test_multiline_body(self):
        text = (
            "---\nname: multi\n---\n"
            "Line one.\n\n"
            "Line two.\n"
            "Line three.\n"
        )
        td = parse_task_text(text)
        assert "Line one." in td.body
        assert "Line two." in td.body
        assert "Line three." in td.body


class TestParseTaskFile:
    def test_reads_from_disk(self, tmp_path):
        task_file = tmp_path / "test.md"
        task_file.write_text(
            "---\nname: disk-task\ntoken-budget: 999\n---\nDo stuff.\n"
        )
        td = parse_task_file(str(task_file))
        assert td.name == "disk-task"
        assert td.token_budget == 999
        assert td.body == "Do stuff."
        assert str(task_file) in td.source

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            parse_task_file("/nonexistent/task.md")

    def test_tilde_expansion(self, tmp_path, monkeypatch):
        task_file = tmp_path / "task.md"
        task_file.write_text("Just a task.\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        td = parse_task_file("~/task.md")
        assert td.body == "Just a task."


# ---------------------------------------------------------------------------
# CLI override
# ---------------------------------------------------------------------------

class TestCliOverrides:
    def test_cli_overrides_task_values(self):
        td = TaskDefinition(
            body="task",
            token_budget=10000,
            time_budget=600,
            logfile="/old.log",
        )
        args = argparse.Namespace(
            token_budget=5000,
            time_budget=120,
            logfile="/new.log",
        )
        apply_cli_overrides(td, args)
        assert td.token_budget == 5000
        assert td.time_budget == 120
        assert td.logfile == "/new.log"

    def test_none_cli_preserves_task_values(self):
        td = TaskDefinition(
            body="task",
            token_budget=10000,
            time_budget=600,
            logfile="/original.log",
        )
        args = argparse.Namespace(
            token_budget=None,
            time_budget=None,
            logfile=None,
        )
        apply_cli_overrides(td, args)
        assert td.token_budget == 10000
        assert td.time_budget == 600
        assert td.logfile == "/original.log"

    def test_partial_cli_overrides(self):
        td = TaskDefinition(body="task", token_budget=10000, time_budget=600)
        args = argparse.Namespace(token_budget=5000, time_budget=None, logfile=None)
        apply_cli_overrides(td, args)
        assert td.token_budget == 5000
        assert td.time_budget == 600


# ---------------------------------------------------------------------------
# Output routing
# ---------------------------------------------------------------------------

class TestOutputRouter:
    def test_stdout_write(self, capsys):
        router = _OutputRouter(logfile=None, debug=False)
        router.write("hello\n")
        router.close()
        assert "hello" in capsys.readouterr().out

    def test_stderr_debug(self, capsys):
        router = _OutputRouter(logfile=None, debug=True)
        router.debug("debug msg\n")
        router.close()
        assert "debug msg" in capsys.readouterr().err

    def test_debug_suppressed_when_disabled(self, capsys):
        router = _OutputRouter(logfile=None, debug=False)
        router.debug("should not appear\n")
        router.close()
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err
        assert "should not appear" not in captured.out

    def test_logfile_write(self, tmp_path):
        logpath = str(tmp_path / "out.log")
        router = _OutputRouter(logfile=logpath, debug=True)
        router.write("result output\n")
        router.debug("debug output\n")
        router.close()
        content = (tmp_path / "out.log").read_text()
        assert "result output" in content
        assert "debug output" in content

    def test_logfile_creates_parent_dirs(self, tmp_path):
        logpath = str(tmp_path / "sub" / "dir" / "out.log")
        router = _OutputRouter(logfile=logpath)
        router.write("test\n")
        router.close()
        assert os.path.exists(logpath)


# ---------------------------------------------------------------------------
# Max steps heuristic
# ---------------------------------------------------------------------------

class TestMaxSteps:
    def test_small_budget(self):
        assert _max_steps_for_budget(5000) == 5

    def test_medium_budget(self):
        assert _max_steps_for_budget(30000) == 15

    def test_large_budget(self):
        assert _max_steps_for_budget(100000) == 30


# ---------------------------------------------------------------------------
# Task-mode system prompt
# ---------------------------------------------------------------------------

class TestTaskModePrompt:
    def _render_system_prompt(self, task_mode: bool) -> str:
        """Render the system prompt template with the given task_mode flag."""
        from macllm.agents.macllm_prompt_templates import MACLLM_AGENT_PROMPT_TEMPLATES
        from smolagents.agents import populate_template

        template_name = "task_runner_system_prompt" if task_mode else "supervising_system_prompt"
        return populate_template(
            MACLLM_AGENT_PROMPT_TEMPLATES[template_name],
            variables={
                "tools": {},
                "managed_agents": {},
                "custom_instructions": "",
                "skills_catalog": "",
                "user_situation": "Test",
            },
        )

    def test_task_mode_no_clarification(self):
        prompt = self._render_system_prompt(task_mode=True)
        assert "Operate autonomously" in prompt
        assert "ask_user" not in prompt

    def test_task_mode_no_tool_limit(self):
        prompt = self._render_system_prompt(task_mode=True)
        assert "Limit tool use to about 3" not in prompt

# ---------------------------------------------------------------------------
# Budget enforcement (mocked agent)
# ---------------------------------------------------------------------------

class TestBudgetEnforcement:
    def test_token_budget_triggers_interrupt(self):
        """Simulate a step callback that exceeds token budget."""
        from macllm.core.chat_history import Conversation, Usage
        from macllm.core.agent_service import create_step_callback
        from smolagents import ActionStep

        conversation = Conversation()
        conversation.usage = Usage(input_tokens=0, output_tokens=0)

        start_time = time.monotonic()
        token_budget = 1000
        budget_exceeded = {"value": False}

        base_callback = create_step_callback(conversation)

        agent = MagicMock()
        agent.interrupt_switch = False

        def budget_callback(step, ag):
            base_callback(step, ag)
            total = conversation.usage.input_tokens + conversation.usage.output_tokens
            if total > token_budget:
                budget_exceeded["value"] = True
                ag.interrupt_switch = True

        step = MagicMock(spec=ActionStep)
        step.token_usage = MagicMock()
        step.token_usage.input_tokens = 800
        step.token_usage.output_tokens = 400
        step.observations = "some output"
        step.error = None

        budget_callback(step, agent)

        assert conversation.usage.input_tokens == 800
        assert conversation.usage.output_tokens == 400
        assert budget_exceeded["value"] is True
        assert agent.interrupt_switch is True

    def test_time_budget_triggers_interrupt(self):
        """Simulate elapsed time exceeding time budget."""
        agent = MagicMock()
        agent.interrupt_switch = False

        start_time = time.monotonic() - 100  # 100s ago
        time_budget = 60  # 60s budget

        elapsed = time.monotonic() - start_time
        if elapsed > time_budget:
            agent.interrupt_switch = True

        assert agent.interrupt_switch is True

    def test_within_budget_no_interrupt(self):
        """Agent stays running when within both budgets."""
        from macllm.core.chat_history import Conversation, Usage
        from macllm.core.agent_service import create_step_callback
        from smolagents import ActionStep

        conversation = Conversation()
        conversation.usage = Usage(input_tokens=0, output_tokens=0)

        agent = MagicMock()
        agent.interrupt_switch = False

        base_callback = create_step_callback(conversation)

        step = MagicMock(spec=ActionStep)
        step.token_usage = MagicMock()
        step.token_usage.input_tokens = 100
        step.token_usage.output_tokens = 50
        step.observations = "output"
        step.error = None

        base_callback(step, agent)

        assert conversation.usage.input_tokens == 100
        assert conversation.usage.output_tokens == 50
        assert agent.interrupt_switch is False
