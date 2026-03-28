"""Shell tool: sandboxed command execution for agents."""

from __future__ import annotations

import os
import subprocess
import time

from smolagents import tool

from macllm.core.command_parser import CommandParseError, extract_executables, extract_paths
from macllm.core.sandbox import run_sandboxed

COMMAND_TIMEOUT = 60

_tool_call_counter = 0


def _make_tool_id() -> str:
    global _tool_call_counter
    _tool_call_counter += 1
    return f"run_command_{_tool_call_counter}_{int(time.time() * 1000)}"


def _status_manager():
    from macllm.macllm import MacLLM

    return MacLLM.get_status_manager()


def _get_conversation():
    from macllm.macllm import MacLLM

    app = MacLLM._instance
    if app is None:
        raise RuntimeError("MacLLM is not initialized")

    if getattr(app, "chat_history", None) is not None:
        return app.chat_history

    if getattr(app, "conversation_history", None) is not None:
        conversation = app.conversation_history.get_current_conversation()
        if conversation is not None:
            return conversation

    raise RuntimeError("No active conversation available for run_command")


def _get_shell_config():
    from macllm.core.config import get_runtime_config

    return get_runtime_config().shell


@tool
def run_command(command: str, working_directory: str = "") -> str:
    """Execute a shell command in a sandboxed environment.

    The command runs with filesystem access restricted to the directories
    that the user has granted access to in this conversation.
    If execution fails for permission reasons, ask the user for next steps.
    Do NOT use this tool to work with notes, use the note subagent instead.

    Args:
        command: The shell command to execute. Pipes and standard shell
            syntax are supported.
        working_directory: Optional working directory for the command.
            Must be inside a granted directory. Defaults to ~/.macllm.

    Returns:
        The command output (stdout, stderr, and exit code).
    """
    tool_id = _make_tool_id()
    status = _status_manager()
    status.start_tool_call(tool_id, "run_command", {"command": command})

    try:
        config = _get_shell_config()
        conversation = _get_conversation()
        granted_dirs = conversation.get_granted_dirs()

        # Parse command to extract executables for whitelist check
        try:
            executables = extract_executables(command)
        except CommandParseError:
            executables = []

        # Check which executables need approval
        allowed = set(config.allowed_commands)
        unknown = [exe for exe in executables if exe not in allowed]
        if not executables:
            unknown = ["(unparseable command)"]

        # Check which paths in the command aren't covered by granted dirs
        cmd_paths = extract_paths(command)
        ungranted = _find_ungranted_paths(cmd_paths, granted_dirs)

        needs_approval = bool(unknown) or bool(ungranted)

        if needs_approval:
            approval = status.request_approval(
                command, unknown, tool_id, ungranted_paths=ungranted,
            )

            entry = _find_entry(status, tool_id)
            if entry:
                entry.status = "pending"
                entry.args_summary = f'"{command}"'

            approval.event.wait()

            if approval.decision == "deny":
                status.fail_tool_call(tool_id, "denied")
                return f"Command denied by user: {command}"

            if approval.decision == "always_allow":
                from macllm.core.config import add_to_shell_allowlist

                for exe in unknown:
                    if exe != "(unparseable command)":
                        add_to_shell_allowlist(exe)

            if approval.decision == "grant_home":
                conversation.grant_directory("~")
                granted_dirs = conversation.get_granted_dirs()
            elif ungranted:
                for path in ungranted:
                    conversation.grant_directory(path)
                granted_dirs = conversation.get_granted_dirs()

        # Resolve working directory
        cwd = _resolve_working_directory(working_directory, granted_dirs)

        # Run under sandbox-exec
        result = run_sandboxed(
            command,
            granted_dirs=granted_dirs,
            read_only_paths=config.read_only_paths,
            cwd=cwd,
            timeout=COMMAND_TIMEOUT,
        )

        output = _format_result(result)

        entry = _find_entry(status, tool_id)
        if entry:
            entry.full_output = output

        exit_info = f"exit {result.returncode}"
        if result.returncode == 0:
            status.complete_tool_call(tool_id, exit_info)
        else:
            status.fail_tool_call(tool_id, exit_info)

        return output

    except subprocess.TimeoutExpired:
        status.fail_tool_call(tool_id, f"timed out after {COMMAND_TIMEOUT}s")
        return f"Command timed out after {COMMAND_TIMEOUT} seconds: {command}"
    except Exception as exc:
        status.fail_tool_call(tool_id, str(exc)[:80])
        raise


def _find_entry(status, tool_id):
    """Look up a ToolCallEntry by id."""
    for entry in status.tool_calls:
        if entry.id == tool_id:
            return entry
    return None


_SANDBOX_OPEN_PREFIXES = (
    "/tmp", "/private/tmp", "/private/var/folders", "/var/folders",
    "/bin", "/usr/bin", "/usr/sbin", "/sbin",
    "/usr/lib", "/usr/local", "/opt/homebrew",
    "/Library", "/System/Library",
    "/private/etc", "/etc", "/var", "/dev",
)


def _find_ungranted_paths(paths: list[str], granted_dirs: list[str]) -> list[str]:
    """Return paths that aren't covered by *granted_dirs* or system prefixes."""
    ungranted: list[str] = []
    for p in paths:
        if any(p.startswith(prefix) for prefix in _SANDBOX_OPEN_PREFIXES):
            continue
        if any(p == g or p.startswith(g + os.sep) for g in granted_dirs):
            continue
        ungranted.append(p)
    return ungranted


_MACLLM_DIR = os.path.expanduser("~/.macllm")


def _resolve_working_directory(requested: str, granted_dirs: list[str]) -> str:
    """Resolve and validate the working directory."""
    if not requested:
        os.makedirs(_MACLLM_DIR, exist_ok=True)
        return _MACLLM_DIR

    expanded = os.path.abspath(os.path.expanduser(requested))

    for granted in granted_dirs:
        if expanded == granted or expanded.startswith(granted + os.sep):
            return expanded

    if expanded.startswith("/tmp") or expanded.startswith("/private/tmp"):
        return expanded

    raise ValueError(
        f"Working directory '{requested}' is not inside a granted directory. "
        f"Granted: {granted_dirs or ['(none — use @path to grant access)']}"
    )


def _format_result(result: subprocess.CompletedProcess) -> str:
    """Format subprocess output for the agent."""
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    if result.returncode != 0:
        parts.append(f"[exit code: {result.returncode}]")
    return "\n".join(parts) if parts else "(no output)"
