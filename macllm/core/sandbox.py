"""macOS Seatbelt sandbox for restricting subprocess filesystem access.

Builds a ``sandbox-exec`` profile and provides a helper to run commands
under ``sandbox-exec -p <profile>``.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

SYSTEM_READ_ONLY_PATHS = [
    "/bin",
    "/usr/bin",
    "/usr/sbin",
    "/sbin",
    "/usr/lib",
    "/usr/local/lib",
    "/usr/local/bin",
    "/usr/local/sbin",
    "/opt/homebrew",
    "/Library",
    "/System/Library",
    "/private/etc",
    "/private/var/db",
    "/etc",
    "/var",
    "/dev",
]

UV_TOOLCHAIN_PATH = "~/.local/share/uv"

TEMP_PATHS = [
    "/tmp",
    "/private/tmp",
    "/private/var/folders",
    "/var/folders",
]

ALWAYS_DENIED_PATHS = [
    "~/.ssh",
    "~/.aws",
    "~/.gnupg",
    "~/.credentials",
    "~/.config/macllm",
]

DEFAULT_READ_ONLY_PATHS = [
    "~/.gitconfig",
    "~/.config/git",
]


_SETUID_SCAN_DIRS = ["/bin", "/usr/bin", "/usr/sbin", "/sbin"]

_setuid_cache: list[str] | None = None


def _find_setuid_binaries() -> list[str]:
    """Scan system binary dirs for setuid executables (cached)."""
    global _setuid_cache
    if _setuid_cache is not None:
        return _setuid_cache
    result: list[str] = []
    for d in _SETUID_SCAN_DIRS:
        try:
            for entry in os.scandir(d):
                try:
                    if entry.is_file(follow_symlinks=False) and entry.stat().st_mode & 0o4000:
                        result.append(entry.path)
                except OSError:
                    continue
        except OSError:
            continue
    _setuid_cache = result
    return result


def _expand(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def _sb_subpath(path: str) -> str:
    """Format a single subpath filter for a sandbox profile."""
    return f'(subpath "{path}")'


def build_profile(
    granted_dirs: list[str],
    read_only_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
) -> str:
    """Build a Seatbelt sandbox profile string.

    Parameters
    ----------
    granted_dirs:
        Directories the process may read and write.
    read_only_paths:
        Additional paths the process may read (beyond system defaults).
    denied_paths:
        Additional paths to deny (beyond the hardcoded sensitive list).
    """
    if read_only_paths is None:
        read_only_paths = DEFAULT_READ_ONLY_PATHS
    if denied_paths is None:
        denied_paths = []

    expanded_granted = [_expand(d) for d in granted_dirs]
    expanded_ro = [_expand(p) for p in read_only_paths]
    expanded_denied = [_expand(p) for p in list(ALWAYS_DENIED_PATHS) + denied_paths]
    expanded_temp = [_expand(p) for p in TEMP_PATHS]

    lines = [
        "(version 1)",
        "(deny default)",
        '(import "bsd.sb")',
        "",
        "(allow process-fork)",
        "(allow process-info*)",
        "(allow sysctl-read)",
        "(allow network*)",
        "",
    ]

    expanded_uv = _expand(UV_TOOLCHAIN_PATH)
    sys_ro = list(SYSTEM_READ_ONLY_PATHS) + ([expanded_uv] if os.path.isdir(expanded_uv) else [])
    sys_subpaths = " ".join(_sb_subpath(p) for p in sys_ro)
    lines.append(f"(allow file-read* process-exec* {sys_subpaths})")

    setuid_bins = _find_setuid_binaries()
    if setuid_bins:
        literals = " ".join(f'(literal "{p}")' for p in setuid_bins)
        lines.append(f"(allow process-exec (with no-sandbox) {literals})")
    lines.append("")

    if expanded_ro:
        ro_subpaths = " ".join(_sb_subpath(p) for p in expanded_ro)
        lines.append(f"(allow file-read* {ro_subpaths})")
        lines.append("")

    if expanded_granted:
        grant_subpaths = " ".join(_sb_subpath(p) for p in expanded_granted)
        lines.append(f"(allow file-read* file-write* {grant_subpaths})")
        lines.append(f"(allow process-exec {grant_subpaths})")
        lines.append("")

    tmp_subpaths = " ".join(_sb_subpath(p) for p in expanded_temp)
    lines.append(f"(allow file-read* file-write* {tmp_subpaths})")
    lines.append("")

    if expanded_denied:
        deny_subpaths = " ".join(_sb_subpath(p) for p in expanded_denied)
        lines.append(f"(deny file-read* file-write* {deny_subpaths})")

    return "\n".join(lines)


_STRIPPED_ENV_VARS = [
    "VIRTUAL_ENV",
    "UV_ENV_FILE",
]


def _clean_env() -> dict[str, str]:
    """Return a copy of ``os.environ`` without macLLM-process-specific vars."""
    return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_VARS}


def run_sandboxed(
    command: str,
    granted_dirs: list[str],
    read_only_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run *command* under ``sandbox-exec`` with the given restrictions.

    Uses ``sandbox-exec -p <profile> /bin/sh -c <command>`` so the
    sandbox is applied by Apple's own binary before the shell starts.
    This is thread-safe (no ``preexec_fn``) and is how Agent Safehouse
    and similar tools implement sandboxing.

    Extra *kwargs* are forwarded to :func:`subprocess.run`.
    """
    profile = build_profile(granted_dirs, read_only_paths, denied_paths)
    kwargs.setdefault("env", _clean_env())
    return subprocess.run(
        ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command],
        capture_output=True,
        text=True,
        **kwargs,
    )
