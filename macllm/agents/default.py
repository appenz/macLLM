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
- Personal, non-public information is often found in the users files (see tool)
- If the user refers to "notes" he means the local files. Use tools to interact with them.
- If you can't find a file right away, always ask for instructions.
- Never create a file without the user's explicit instructions.
- If a user asks you to append to a file, you may NEVER create a file with that name. Instead ask the user for instructions.

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
        "search_files",
        "read_full_file",
        "file_append",
        "file_create",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=CUSTOM_INSTRUCTIONS,
            prompt_templates=PROMPT_TEMPLATES,
            **kwargs,
        )
