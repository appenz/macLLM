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
- Personal, non-public information is often found in the user's files. Delegate file tasks to your files team member.
- If the user refers to "notes" he means local files. Use the files team member to interact with them.
- For anything related to calendar, meetings, events, scheduling, or free time, delegate to your calendar team member.
- For anything related to Things, to-dos, task management, projects, areas, tags, inboxes, or logbooks, delegate to your things team member.
- When a task might match an available skill, call read_skill with the skill name to retrieve its full instructions.
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
        "read_skill",
    ]
    macllm_managed_agents = ["files", "calendar", "things"]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=CUSTOM_INSTRUCTIONS,
            prompt_templates=PROMPT_TEMPLATES,
            **kwargs,
        )
