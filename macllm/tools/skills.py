from pathlib import Path

from smolagents import tool

from macllm.core.skills import SkillsRegistry

MAX_SKILL_FILE_LEN = 10_000


def _list_skill_files(skill_dir: Path, exclude: Path) -> list[str]:
    """Return sorted relative paths of all files in *skill_dir*, excluding *exclude*."""
    files = []
    for p in sorted(skill_dir.rglob("*")):
        if p.is_file() and p != exclude:
            files.append(str(p.relative_to(skill_dir)))
    return files


def _read_skill_file(skill_dir: Path, file: str) -> str:
    """Read a file from *skill_dir* with path-traversal protection."""
    target = (skill_dir / file).resolve()
    if not str(target).startswith(str(skill_dir.resolve())):
        return f"Error: path '{file}' escapes the skill directory."
    if not target.is_file():
        return f"Error: file '{file}' not found in skill directory."
    try:
        content = target.read_text(encoding="utf-8")[:MAX_SKILL_FILE_LEN]
    except Exception as exc:
        return f"Error reading '{file}': {exc}"
    return content


@tool
def read_skill(name: str, file: str = "") -> str:
    """
    Read a model-invocable skill or a file from its directory.

    Args:
        name: Skill name without leading slash (for example: "emoji").
        file: Optional relative path to a file in the skill directory
              (for example: "references/workflows.md").
              If empty, returns the skill body and lists available files.

    Returns:
        Skill body with a file listing, or the content of the requested file.
    """
    SkillsRegistry.ensure_loaded()

    skill = SkillsRegistry.get_model_invocable(name.strip())
    if skill is None:
        return f"Skill '{name}' is unavailable or not model-invocable."

    skill_dir = Path(skill.source).parent

    if file.strip():
        return _read_skill_file(skill_dir, file.strip())

    result = (
        f"Skill: {skill.name}\n"
        f"Description: {skill.description}\n\n"
        f"{skill.body}"
    )

    extra_files = _list_skill_files(skill_dir, Path(skill.source))
    if extra_files:
        listing = "\n".join(f"- {f}" for f in extra_files)
        result += (
            f"\n\n---\n"
            f"Skill files, to read use read_skill(\"{skill.name}\", file=...)\n"
            f"{listing}"
        )

    return result
