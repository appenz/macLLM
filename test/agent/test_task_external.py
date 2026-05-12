"""External tests for the task runner — hits real LLM APIs."""

import os
import subprocess
import sys
import tempfile

import pytest


@pytest.mark.external
class TestTaskRunnerExternal:
    """End-to-end task execution with a real LLM."""

    @pytest.fixture
    def package_root(self):
        return os.path.join(os.path.dirname(__file__), '..', '..')

    def test_simple_task_completes(self, package_root, tmp_path):
        task_file = tmp_path / "simple.md"
        task_file.write_text("What is 2 + 2? Reply with only the number.\n")

        result = subprocess.run(
            [sys.executable, "-m", "macllm", "-task", str(task_file)],
            capture_output=True,
            text=True,
            cwd=package_root,
            timeout=120,
        )

        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert result.stdout.strip(), "Expected some output"

    def test_task_with_logfile(self, package_root, tmp_path):
        task_file = tmp_path / "logged.md"
        logfile = tmp_path / "output.log"
        task_file.write_text(
            f"---\nname: logged-task\nlogfile: {logfile}\n---\n"
            "What is the capital of France? Reply with only the city name.\n"
        )

        result = subprocess.run(
            [sys.executable, "-m", "macllm", "-task", str(task_file)],
            capture_output=True,
            text=True,
            cwd=package_root,
            timeout=120,
        )

        assert result.returncode == 0
        assert logfile.exists(), "Logfile should have been created"
        content = logfile.read_text()
        assert content.strip(), "Logfile should contain output"

    def test_task_with_small_token_budget(self, package_root, tmp_path):
        task_file = tmp_path / "budgeted.md"
        task_file.write_text(
            "---\ntoken-budget: 500\n---\n"
            "What is the meaning of life? Give a detailed philosophical analysis.\n"
        )

        result = subprocess.run(
            [sys.executable, "-m", "macllm", "-task", str(task_file)],
            capture_output=True,
            text=True,
            cwd=package_root,
            timeout=120,
        )

        # Should still exit 0 even with budget exceeded
        assert result.returncode == 0

    def test_cli_budget_override(self, package_root, tmp_path):
        task_file = tmp_path / "override.md"
        task_file.write_text(
            "---\ntoken-budget: 999999\n---\n"
            "What is 1 + 1? Reply with only the number.\n"
        )

        result = subprocess.run(
            [sys.executable, "-m", "macllm", "-task", str(task_file),
             "--token-budget", "500"],
            capture_output=True,
            text=True,
            cwd=package_root,
            timeout=120,
        )

        assert result.returncode == 0

    def test_missing_task_file_exits_1(self, package_root):
        result = subprocess.run(
            [sys.executable, "-m", "macllm", "-task", "/nonexistent/task.md"],
            capture_output=True,
            text=True,
            cwd=package_root,
            timeout=30,
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()
