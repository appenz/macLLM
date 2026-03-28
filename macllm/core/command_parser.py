"""Extract executable names from shell command strings using bashlex."""

from __future__ import annotations

import os


class CommandParseError(Exception):
    """Raised when a shell command cannot be parsed."""


def extract_executables(command: str) -> list[str]:
    """Parse *command* and return a deduplicated list of executable names.

    Uses ``bashlex`` to build an AST and walks it to find every command
    node.  For each command the first word (the executable) is collected.

    Raises :class:`CommandParseError` if *command* is empty or cannot be
    parsed.
    """
    import bashlex

    command = command.strip()
    if not command:
        raise CommandParseError("Empty command")

    try:
        parts = bashlex.parse(command)
    except Exception as exc:
        raise CommandParseError(f"Failed to parse command: {exc}") from exc

    executables: list[str] = []
    for node in parts:
        _walk(node, executables)

    seen: set[str] = set()
    result: list[str] = []
    for exe in executables:
        if exe not in seen:
            seen.add(exe)
            result.append(exe)
    return result


def _walk(node, executables: list[str]) -> None:
    """Recursively walk a bashlex AST node collecting executable names."""
    kind = node.kind

    if kind == "command":
        _extract_command_name(node, executables)
        for part in getattr(node, "parts", []):
            _walk_word(part, executables)
        return

    if kind in ("list", "pipeline"):
        for part in node.parts:
            if hasattr(part, "kind") and part.kind != "operator":
                _walk(part, executables)
        return

    if kind == "compound":
        for part in node.parts:
            _walk(part, executables)
        return

    if kind == "commandsubstitution":
        cmd = getattr(node, "command", None)
        if cmd is not None:
            _walk(cmd, executables)
        return

    for child in getattr(node, "parts", []):
        _walk(child, executables)


def _walk_word(node, executables: list[str]) -> None:
    """Walk into word nodes looking for nested command substitutions."""
    if node.kind == "commandsubstitution":
        cmd = getattr(node, "command", None)
        if cmd is not None:
            _walk(cmd, executables)
        return

    for part in getattr(node, "parts", []):
        _walk_word(part, executables)


def _extract_command_name(node, executables: list[str]) -> None:
    """Extract the executable name from a command node.

    Skips leading variable assignments (``FOO=bar cmd``) and extracts the
    basename when the command uses an absolute path.
    """
    for part in getattr(node, "parts", []):
        if part.kind == "assignment":
            continue
        if part.kind == "word":
            name = part.word
            if "/" in name:
                name = os.path.basename(name)
            if name:
                executables.append(name)
            return
        return


def extract_paths(command: str) -> list[str]:
    """Parse *command* and return a deduplicated list of path-like arguments.

    Walks the ``bashlex`` AST and collects word nodes that look like
    filesystem paths (starting with ``/``, ``~``, ``./``, or ``../``).
    Skips the executable itself (the first word of each command).

    Returns expanded, absolute paths.  Returns an empty list if parsing
    fails.
    """
    import bashlex

    command = command.strip()
    if not command:
        return []

    try:
        parts = bashlex.parse(command)
    except Exception:
        return []

    raw_paths: list[str] = []
    for node in parts:
        _walk_paths(node, raw_paths)

    seen: set[str] = set()
    result: list[str] = []
    for p in raw_paths:
        expanded = os.path.abspath(os.path.expanduser(p))
        if expanded not in seen:
            seen.add(expanded)
            result.append(expanded)
    return result


def _walk_paths(node, paths: list[str]) -> None:
    """Recursively walk a bashlex AST collecting path-like arguments."""
    kind = node.kind

    if kind == "command":
        _collect_path_args(node, paths)
        return

    if kind in ("list", "pipeline"):
        for part in node.parts:
            if hasattr(part, "kind") and part.kind != "operator":
                _walk_paths(part, paths)
        return

    if kind == "compound":
        for part in node.parts:
            _walk_paths(part, paths)
        return

    if kind == "commandsubstitution":
        cmd = getattr(node, "command", None)
        if cmd is not None:
            _walk_paths(cmd, paths)
        return

    for child in getattr(node, "parts", []):
        _walk_paths(child, paths)


def _is_path_like(word: str) -> bool:
    """Return True if *word* looks like a filesystem path."""
    return word.startswith(("/", "~/", "~", "./", "../"))


def _collect_path_args(node, paths: list[str]) -> None:
    """Collect path-like arguments from a command node, skipping the executable."""
    found_executable = False
    for part in getattr(node, "parts", []):
        if part.kind == "assignment":
            continue
        if part.kind == "word":
            if not found_executable:
                found_executable = True
                continue
            if _is_path_like(part.word):
                paths.append(part.word)
        if part.kind == "commandsubstitution":
            cmd = getattr(part, "command", None)
            if cmd is not None:
                _walk_paths(cmd, paths)
