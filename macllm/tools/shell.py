"""Shell tool: sandboxed command execution for agents."""

from __future__ import annotations

import os
import subprocess

from macllm.core.command_parser import CommandParseError, extract_executables, extract_paths
from macllm.core.sandbox import run_sandboxed
from macllm.tools._debug import macllm_tool, set_tool_message

COMMAND_TIMEOUT = 60


def _cmd_preview(cmd: str) -> str:
    c = cmd.replace("\n", " ")
    return c if len(c) <= 60 else c[:57] + "..."


def _debug_log(message: str, level: int = 0) -> None:
    from macllm.macllm import MacLLM

    app = MacLLM._instance
    if app is not None:
        app.debug_log(message, level)


def _get_conversation():
    from macllm.core.context import get_current_conversation
    return get_current_conversation()


def _get_shell_config():
    from macllm.core.config import get_runtime_config

    return get_runtime_config().shell


@macllm_tool
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
    try:
        config = _get_shell_config()
        conversation = _get_conversation()
        granted_dirs = conversation.get_granted_dirs()

        try:
            executables = extract_executables(command)
        except CommandParseError:
            executables = []

        allowed = set(config.allowed_commands)
        unknown = [exe for exe in executables if exe not in allowed]
        if not executables:
            unknown = ["(unparseable command)"]

        cmd_paths = extract_paths(command)
        ungranted = _find_ungranted_paths(cmd_paths, granted_dirs)

        needs_approval = bool(unknown) or bool(ungranted)

        if needs_approval:
            conversation.pop_last_tool_call()
            from macllm.core.agent_status import PendingApproval

            approval = PendingApproval(
                command=command,
                unknown_executables=unknown,
                tool_call_id="",
                ungranted_paths=ungranted,
            )
            conversation.pending_approval = approval
            conversation._notify_ui()

            approval.event.wait()
            conversation.pending_approval = None
            conversation._notify_ui()

            if approval.decision == "deny":
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

            conversation.add_tool_call("run_command", _cmd_preview(command))
        else:
            set_tool_message(_cmd_preview(command))

        cwd = _resolve_working_directory(working_directory, granted_dirs)

        result = run_sandboxed(
            command,
            granted_dirs=granted_dirs,
            read_only_paths=config.read_only_paths,
            cwd=cwd,
            timeout=COMMAND_TIMEOUT,
        )

        output = _format_result(result)

        if result.returncode != 0:
            _debug_log(f"Shell: exit {result.returncode} — {command!r} (cwd={cwd})", 2)
            if result.stderr:
                _debug_log(f"Shell stderr: {result.stderr.rstrip()}", 2)

        return output

    except subprocess.TimeoutExpired:
        _debug_log(f"Shell: timed out after {COMMAND_TIMEOUT}s: {command!r}", 2)
        return f"Command timed out after {COMMAND_TIMEOUT} seconds: {command}"
    except Exception as exc:
        _debug_log(f"Shell: exception: {exc}", 2)
        raise


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
