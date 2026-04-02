from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import tomllib


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class ApiKeys:
    openai: str = ""
    inception: str = ""
    brave: str = ""
    gemini: str = ""


@dataclass
class ShellConfig:
    allowed_commands: list[str] = field(default_factory=list)
    default_dirs: list[str] = field(default_factory=list)
    read_only_paths: list[str] = field(default_factory=list)


@dataclass
class MacLLMConfig:
    api_keys: ApiKeys = field(default_factory=ApiKeys)
    skills_dirs: list[str] = field(default_factory=list)
    index_dirs: list[str] = field(default_factory=list)
    memory_dir: str = ""
    shell: ShellConfig = field(default_factory=ShellConfig)

    def resolved_skills_dirs(self, project_root: Path | None = None) -> list[str]:
        return _resolve_paths(self.skills_dirs, project_root)

    def resolved_index_dirs(self, project_root: Path | None = None) -> list[str]:
        return _resolve_paths(self.index_dirs, project_root)

    def resolved_memory_dir(self, project_root: Path | None = None) -> str:
        """Return the absolute memory directory path, or ``""`` if unset."""
        if not self.memory_dir:
            return ""
        resolved = _resolve_paths([self.memory_dir], project_root)
        return resolved[0] if resolved else ""


_RUNTIME_CONFIG: MacLLMConfig | None = None


def _resolve_paths(values: list[str], project_root: Path | None = None) -> list[str]:
    root = project_root or _project_root()
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        p = Path(expanded)
        if not p.is_absolute():
            p = (root / p).resolve()
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Merge policy:
    - Scalars: override wins
    - Dicts: recursive merge
    - Lists: override list replaces base list
    """
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


_DEFAULT_ALLOWED_COMMANDS = [
    "ls", "cat", "head", "tail", "wc", "grep", "find",
    "sort", "uniq", "diff", "echo", "printf",
    "mkdir", "cp", "mv", "touch", "pwd",
]

_DEFAULT_DIRS = [
    "~/.macllm",
    "~/Downloads",
    "~/tmp",
]

_DEFAULT_READ_ONLY_PATHS = [
    "~/.gitconfig",
    "~/.config/git",
]


def _from_dict(data: dict[str, Any]) -> MacLLMConfig:
    api = data.get("api_keys", {}) or {}
    shell_data = data.get("shell", {}) or {}
    return MacLLMConfig(
        api_keys=ApiKeys(
            openai=str(api.get("openai", "") or ""),
            inception=str(api.get("inception", "") or ""),
            brave=str(api.get("brave", "") or ""),
            gemini=str(api.get("gemini", "") or ""),
        ),
        skills_dirs=[str(x) for x in (data.get("skills_dirs", []) or [])],
        index_dirs=[str(x) for x in (data.get("index_dirs", []) or [])],
        memory_dir=str(data.get("memory_dir", "") or ""),
        shell=ShellConfig(
            allowed_commands=shell_data.get("allowed_commands")
            or list(_DEFAULT_ALLOWED_COMMANDS),
            default_dirs=shell_data.get("default_dirs")
            or list(_DEFAULT_DIRS),
            read_only_paths=shell_data.get("read_only_paths")
            or list(_DEFAULT_READ_ONLY_PATHS),
        ),
    )


def load_config(project_root: Path | None = None) -> MacLLMConfig:
    root = project_root or _project_root()
    project_config = _load_toml(root / "config" / "config.toml")
    user_config = _load_toml(Path("~/.config/macllm/config.toml").expanduser())
    merged = _deep_merge(project_config, user_config)
    return _from_dict(merged)


def load_runtime_config(project_root: Path | None = None) -> MacLLMConfig:
    global _RUNTIME_CONFIG
    _RUNTIME_CONFIG = load_config(project_root=project_root)
    return _RUNTIME_CONFIG


def get_runtime_config(project_root: Path | None = None) -> MacLLMConfig:
    global _RUNTIME_CONFIG
    if _RUNTIME_CONFIG is None:
        _RUNTIME_CONFIG = load_config(project_root=project_root)
    return _RUNTIME_CONFIG


def add_to_shell_allowlist(command: str) -> None:
    """Persist *command* to the user-level shell allowlist.

    Reads ``~/.config/macllm/config.toml``, appends *command* to the
    ``[shell] allowed_commands`` list, and writes the file back.  Also
    updates the in-memory runtime config so the change takes effect
    immediately.
    """
    user_path = Path("~/.config/macllm/config.toml").expanduser()
    user_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = _load_toml(user_path) if user_path.exists() else {}
    shell_section = data.setdefault("shell", {})
    existing: list[str] = shell_section.get("allowed_commands", [])
    if command not in existing:
        existing.append(command)
    shell_section["allowed_commands"] = existing

    import tomli_w
    with user_path.open("wb") as f:
        tomli_w.dump(data, f)

    global _RUNTIME_CONFIG
    if _RUNTIME_CONFIG is not None and command not in _RUNTIME_CONFIG.shell.allowed_commands:
        _RUNTIME_CONFIG.shell.allowed_commands.append(command)
