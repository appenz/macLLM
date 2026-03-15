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
- For anything related to Granola meeting notes, transcripts, or meeting attendees from Granola, delegate to your granola team member.
- When the user wants to see a list of their Granola meetings or notes, delegate to your granola team member with "LIST_ALL" as the task.
- When presenting a Granola meeting table returned by the granola team member, include it exactly as received without reformatting.

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
    ]
    macllm_managed_agents = ["files", "calendar", "granola"]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=CUSTOM_INSTRUCTIONS,
            prompt_templates=PROMPT_TEMPLATES,
            **kwargs,
        )
