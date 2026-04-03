from pathlib import Path

import yaml

from macllm.agents.base import MacLLMAgent

CUSTOM_INSTRUCTIONS = """\
You are a helpful assistant.
- If the request refers to a context:... this is a reference to a context block.
- In most cases, you dont need to mention the context explicitly.
- If you refer to it, do it by name only. So for "context:clipboard" just say "the clipboard"
- If asked to just look at a context, just acknowledge it. A question will follow later.
- If the user's request is not clear, ask for clarification.
- Always use the notes team member for any note-related operation (reading, searching, creating, modifying, listing, etc.). Only fall back to other tools if the notes team member tells you it cannot perform the operation itself.
- When the user refers to "notes" or "files" they mean local indexed notes.
- For anything related to calendar, meetings, events, scheduling, or free time, delegate to your calendar team member.
- For anything related to Things, to-dos, task management, projects, areas, tags, inboxes, or logbooks, delegate to your things team member.
- When a task might match an available skill, call read_skill with the skill name to retrieve its full instructions.
- Use remember to save important facts, preferences, or decisions the user shares that are worth recalling in future conversations.
"""

_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_TEMPLATES = yaml.safe_load((_PROMPTS_DIR / "default.yaml").read_text())


class MacLLMDefaultAgent(MacLLMAgent):
    """General-purpose macLLM assistant.

    Uses a local copy of the prompt templates from
    ``macllm/agents/prompts/default.yaml`` — edit that file to customise the
    system prompt, planning prompts, managed-agent prompts, etc.
    """

    macllm_name = "default"
    macllm_description = "General-purpose macLLM assistant"
    macllm_tools = [
        "get_current_time",
        "web_search",
        "run_command",
        "read_skill",
        "remember",
    ]
    macllm_managed_agents = ["notes", "calendar", "things"]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=CUSTOM_INSTRUCTIONS,
            prompt_templates=PROMPT_TEMPLATES,
            **kwargs,
        )
