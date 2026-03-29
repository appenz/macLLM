from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re

from macllm.core.config import get_runtime_config


@dataclass
class Skill:
    name: str
    description: str
    disable_model_invocation: bool
    body: str
    source: str

    @property
    def command(self) -> str:
        return f"/{self.name}"


class SkillsRegistry:
    _skills: dict[str, Skill] = {}
    _errors: list[str] = []
    _loaded = False
    _last_summary = ""
    _builtin_commands = ["/reload"]

    @classmethod
    def reload(cls) -> str:
        cfg = get_runtime_config()
        cls._skills = {}
        cls._errors = []

        loaded_files = 0
        for dir_path in cfg.resolved_skills_dirs():
            root = Path(dir_path)
            if not root.exists() or not root.is_dir():
                continue
            for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
                for fn in sorted(filenames):
                    if fn.endswith(".md"):
                        loaded_files += 1
                        cls._load_markdown_file(Path(dirpath) / fn)

        cls._loaded = True
        cls._last_summary = (
            f"Skills reloaded: {len(cls._skills)} skills from {loaded_files} files"
        )
        if cls._errors:
            cls._last_summary += f" ({len(cls._errors)} parse warnings)"
        names = ", ".join(sorted(cls._skills.keys())) or "(none)"
        try:
            from macllm.macllm import MacLLM
            if MacLLM._instance is not None:
                MacLLM._instance.debug_log(f"[skills] {cls._last_summary}: {names}")
        except Exception:
            pass
        return cls._last_summary

    @classmethod
    def ensure_loaded(cls):
        if not cls._loaded:
            cls.reload()

    @classmethod
    def list_all(cls) -> list[Skill]:
        cls.ensure_loaded()
        return [cls._skills[k] for k in sorted(cls._skills.keys())]

    @classmethod
    def list_model_invocable(cls) -> list[Skill]:
        return [s for s in cls.list_all() if not s.disable_model_invocation]

    @classmethod
    def list_manual_commands(cls) -> list[str]:
        cls.ensure_loaded()
        cmds = [f"/{name}" for name in sorted(cls._skills.keys())]
        return sorted(set(cmds + cls._builtin_commands))

    @classmethod
    def get(cls, name: str) -> Skill | None:
        cls.ensure_loaded()
        return cls._skills.get(name)

    @classmethod
    def get_model_invocable(cls, name: str) -> Skill | None:
        skill = cls.get(name)
        if skill is None or skill.disable_model_invocation:
            return None
        return skill

    @classmethod
    def expand_manual_invocation(cls, text: str) -> str:
        """
        Expand a leading slash skill invocation:
          /skill arg text
        to:
          <skill body>

          ARGUMENTS: arg text
        """
        cls.ensure_loaded()
        stripped = text.strip()
        if not stripped.startswith("/"):
            return text
        token, sep, rest = stripped.partition(" ")
        name = token[1:]
        skill = cls.get(name)
        if skill is None:
            return text
        expanded = skill.body.strip()
        if rest.strip():
            expanded += f"\n\nARGUMENTS: {rest.strip()}"
        return expanded

    @classmethod
    def model_catalog_text(cls, max_chars: int = 5000) -> str:
        cls.ensure_loaded()
        lines = [
            f"- {s.name}: {s.description}"
            for s in cls.list_model_invocable()
        ]
        if not lines:
            return "No model-invocable skills are currently available."
        out = "Available skills (use read_skill to fetch full instructions):\n" + "\n".join(lines)
        if len(out) <= max_chars:
            return out
        return out[: max_chars - 20] + "\n... [truncated]"

    @classmethod
    def _load_markdown_file(cls, path: Path):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            cls._errors.append(f"Failed to read {path}: {exc}")
            return

        parsed = _parse_skills_from_markdown(text, str(path))
        for skill in parsed:
            # Last writer wins; this naturally allows user dir overrides
            cls._skills[skill.name] = skill


_FRONTMATTER_RE = re.compile(r"(?m)^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def _parse_bool(raw: str, default: bool = False) -> bool:
    v = raw.strip().lower()
    if v in ("true", "yes", "1"):
        return True
    if v in ("false", "no", "0"):
        return False
    return default


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        k = key.strip()
        v = value.strip()
        if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
            v = v[1:-1]
        data[k] = v
    return data


def _parse_skills_from_markdown(text: str, source: str) -> list[Skill]:
    matches = list(_FRONTMATTER_RE.finditer(text))
    if not matches:
        return []

    skills: list[Skill] = []
    for idx, m in enumerate(matches):
        fm = _parse_frontmatter(m.group(1))
        name = fm.get("name", "").strip()
        description = fm.get("description", "").strip()
        disable = _parse_bool(fm.get("disable-model-invocation", "false"))
        if not name:
            continue
        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        skills.append(
            Skill(
                name=name,
                description=description,
                disable_model_invocation=disable,
                body=body,
                source=source,
            )
        )
    return skills
