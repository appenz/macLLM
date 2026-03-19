from smolagents import tool

from macllm.core.skills import SkillsRegistry


@tool
def read_skill(name: str = "") -> str:
    """
    Read full instructions for a model-invocable skill by name.

    Args:
        name: Skill name without leading slash (for example: "emoji").
              If empty, returns the list of model-invocable skills.

    Returns:
        Skill details including name, description, and full instructions.
    """
    SkillsRegistry.ensure_loaded()
    if not name.strip():
        skills = SkillsRegistry.list_model_invocable()
        if not skills:
            return "No model-invocable skills are available."
        lines = [f"- {s.name}: {s.description}" for s in skills]
        return "Model-invocable skills:\n" + "\n".join(lines)

    skill = SkillsRegistry.get_model_invocable(name.strip())
    if skill is None:
        return f"Skill '{name}' is unavailable or not model-invocable."

    return (
        f"Skill: {skill.name}\n"
        f"Description: {skill.description}\n\n"
        f"{skill.body}"
    )
