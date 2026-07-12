from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from macllm.core.virtual_filesystem import configured_mounts, skill_virtual_path

# Cursor-style packs: only SKILL.md in an immediate subfolder of each skills root is loaded
# from that folder; see SkillsRegistry.reload().
SKILL_FILENAME = "SKILL.md"


@dataclass
class Skill:
    name: str
    description: str
    disable_model_invocation: bool
    user_invocable: bool
    body: str
    source: str

    @property
    def command(self) -> str:
        return f"/{self.name}"


def _skills_debug_log(message: str, level: int = 0) -> None:
    """Log only when MacLLM is up and ``--debug`` is enabled."""
    try:
        from macllm.macllm import MacLLM

        inst = MacLLM._instance
        if inst is not None:
            inst.debug_log(message, level)
    except Exception:
        pass


class SkillsRegistry:
    _skills: dict[str, Skill] = {}
    _errors: list[str] = []
    _loaded = False
    _last_summary = ""
    _builtin_commands = ["/reload"]

    @classmethod
    def reload(cls) -> str:
        cls._skills = {}
        cls._errors = []

        loaded_files = 0
        for mount in configured_mounts():
            if not (mount.virtual == "/skills" or mount.virtual.startswith("/skills/")):
                continue
            root = mount.host
            if not root.exists() or not root.is_dir():
                _skills_debug_log(
                    f"[skills] skip (missing or not a directory): {root}", 1
                )
                continue
            try:
                for path in sorted(root.glob("*.md"), key=lambda p: p.name.lower()):
                    loaded_files += 1
                    cls._load_markdown_file(path)
                subs = sorted(
                    (p for p in root.iterdir() if p.is_dir()),
                    key=lambda p: p.name.lower(),
                )
                for sub in subs:
                    skill_md = sub / SKILL_FILENAME
                    if skill_md.is_file():
                        loaded_files += 1
                        cls._load_markdown_file(skill_md)
            except OSError as exc:
                cls._errors.append(f"Skills scan failed in {root}: {exc}")

        cls._loaded = True
        cls._last_summary = (
            f"Skills reloaded: {len(cls._skills)} skills from {loaded_files} files"
        )
        if cls._errors:
            cls._last_summary += f" ({len(cls._errors)} parse warnings)"
        names = ", ".join(sorted(cls._skills.keys())) or "(none)"
        _skills_debug_log(f"[skills] {cls._last_summary}: {names}")
        for err in cls._errors:
            _skills_debug_log(f"[skills] {err}", 2)
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
        cmds = [f"/{s.name}" for s in cls._skills.values() if s.user_invocable]
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
        Expand manual slash skill invocations.

        A leading slash skill invocation:
          /skill arg text
        to:
          <skill body>

          ARGUMENTS: arg text

        Later occurrences of /skill are replaced inline with the skill body.
        """
        cls.ensure_loaded()
        stripped = text.strip()
        if stripped.startswith("/"):
            token, sep, rest = stripped.partition(" ")
            name = token[1:]
            skill = cls.get(name)
            if skill is not None and skill.user_invocable:
                expanded = skill.body.strip()
                if rest.strip():
                    rest = cls.expand_inline_manual_invocations(rest)
                    expanded += f"\n\nARGUMENTS: {rest.strip()}"
                if not expanded.strip():
                    return text
                return expanded
        return cls.expand_inline_manual_invocations(text)

    @classmethod
    def expand_inline_manual_invocations(cls, text: str) -> str:
        """Replace user-invocable /skill tokens anywhere in the prompt."""
        from macllm.core.user_request import UserRequest

        shortcuts = [
            (start, end, shortcut_text)
            for start, end, shortcut_text in UserRequest.find_shortcuts(text)
            if shortcut_text.startswith("/")
        ]
        if not shortcuts:
            return text

        expanded_text = text
        for start, end, shortcut_text in reversed(shortcuts):
            name = shortcut_text[1:]
            skill = cls.get(name)
            if skill is None or not skill.user_invocable:
                continue
            body = skill.body.strip()
            if not body:
                continue
            expanded_text = expanded_text[:start] + body + expanded_text[end:]
        return expanded_text

    @classmethod
    def _plugin_slash_prefixes(cls, plugins) -> set[str]:
        """Slash tokens owned by builtins or tag plugins (not skill expansion)."""
        out: set[str] = set(cls._builtin_commands)
        if not plugins:
            return out
        for plugin in plugins:
            try:
                for prefix in plugin.get_prefixes():
                    if prefix.startswith("/"):
                        out.add(prefix)
            except Exception:
                continue
        return out

    @classmethod
    def failed_leading_slash_skill_message(
        cls, user_input: str, after_skill_expand: str, plugins
    ) -> str | None:
        """If a leading /command did not expand as a skill, return a user-visible error.

        Builtin and tag-plugin slash commands (e.g. /reload, /fast) return None.
        """
        if after_skill_expand != user_input:
            return None
        if not user_input.startswith("/"):
            return None
        token, _, _ = user_input.partition(" ")
        if len(token) <= 1:
            return None
        name = token[1:]
        skill = cls.get(name)
        if skill is not None and skill.user_invocable:
            if not skill.body.strip():
                return (
                    f"Skill {name!r} has an empty instruction body. "
                    "If you use a markdown horizontal rule, avoid a bare '---' line "
                    "in older files; use '***' or underline headings instead."
                )
            return (
                f"Skill {name!r} is marked user-invocable but did not expand; "
                "this is an internal error — please report."
            )
        if skill is not None and not skill.user_invocable:
            return (
                f"Skill {name!r} is loaded but cannot be invoked with / "
                "(user-invocable: false)."
            )
        if token in cls._plugin_slash_prefixes(plugins):
            return None
        return (
            f"No skill named {name!r} is loaded. Try /reload to refresh skills, or "
            f"check that your skill markdown defines name: {name}."
        )

    @classmethod
    def model_catalog_text(cls, names: list[str] | None = None,
                           max_chars: int = 5000) -> str:
        cls.ensure_loaded()
        skills = cls.list_model_invocable()
        if names is not None:
            allowed = set(names)
            skills = [s for s in skills if s.name in allowed]
        lines = []
        for skill in skills:
            virtual = skill_virtual_path(skill.source)
            if virtual is None:
                error = f"Skill source is outside configured /skills mounts: {skill.source}"
                if error not in cls._errors:
                    cls._errors.append(error)
                continue
            lines.append(f"- {skill.name}: {skill.description} ({virtual})")
        if not lines:
            return "No model-invocable skills are currently available."
        out = "Available skills (use read_file on the listed path):\n" + "\n".join(lines)
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

        pack_dir_name = (
            path.parent.name
            if path.name.lower() == SKILL_FILENAME.lower()
            else None
        )
        try:
            parsed = _parse_skills_from_markdown(
                text, str(path), pack_directory_name=pack_dir_name
            )
        except ValueError as exc:
            cls._errors.append(str(exc))
            return
        if not parsed:
            # Plain markdown (no ---/YAML blocks) is normal for reference docs; do not warn.
            # Warn only when the file looks like a skill attempt but no block has name:.
            if list(_FRONTMATTER_RE.finditer(text)):
                _skills_debug_log(
                    f"[skills] no named skills parsed from {path} "
                    "(each skill needs a --- block with name: …; see specs/skills.md)",
                    1,
                )
            return
        for skill in parsed:
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


def _parse_skills_from_markdown(
    text: str,
    source: str,
    pack_directory_name: str | None = None,
) -> list[Skill]:
    matches = list(_FRONTMATTER_RE.finditer(text))
    if not matches:
        return []

    # Only treat ---…--- blocks as skill boundaries when frontmatter declares
    # name:. Otherwise a markdown horizontal rule ("---" on its own line) in
    # the body would split the skill and leave an empty body (see /emoji vs
    # templates that use --- dividers).
    skill_matches = [
        m
        for m in matches
        if _parse_frontmatter(m.group(1)).get("name", "").strip()
    ]

    # Cursor-style pack: <dir>/SKILL.md may omit name: — use the folder name.
    # One skill from the first YAML block; body is the rest of the file (other
    # --- lines stay in the body as markdown).
    if not skill_matches and pack_directory_name:
        m0 = matches[0]
        fm0 = _parse_frontmatter(m0.group(1))
        explicit_name = fm0.get("name", "").strip()
        name = explicit_name or pack_directory_name
        if not explicit_name:
            _skills_debug_log(
                f"[skills] warning: {source} has no name: in frontmatter; "
                f"using folder name {pack_directory_name!r} as skill id "
                "(add an explicit name: to match / commands and avoid surprises)",
                3,
            )
        description = fm0.get("description", "").strip()
        disable = _parse_bool(fm0.get("disable-model-invocation", "false"))
        user_invocable = _parse_bool(fm0.get("user-invocable", "true"), default=True)
        body = text[m0.end() :].strip()
        return [
            Skill(
                name=name,
                description=description,
                disable_model_invocation=disable,
                user_invocable=user_invocable,
                body=body,
                source=source,
            )
        ]

    if not skill_matches:
        return []

    skills: list[Skill] = []
    seen: set[str] = set()
    for idx, m in enumerate(skill_matches):
        fm = _parse_frontmatter(m.group(1))
        name = fm.get("name", "").strip()
        description = fm.get("description", "").strip()
        disable = _parse_bool(fm.get("disable-model-invocation", "false"))
        user_invocable = _parse_bool(fm.get("user-invocable", "true"), default=True)
        body_start = m.end()
        body_end = (
            skill_matches[idx + 1].start()
            if idx + 1 < len(skill_matches)
            else len(text)
        )
        body = text[body_start:body_end].strip()
        if name in seen:
            raise ValueError(
                f"Duplicate skill name {name!r} in the same file ({source})"
            )
        seen.add(name)
        skills.append(
            Skill(
                name=name,
                description=description,
                disable_model_invocation=disable,
                user_invocable=user_invocable,
                body=body,
                source=source,
            )
        )
    return skills
