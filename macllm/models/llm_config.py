from dataclasses import dataclass

# Class to store the specific configuration of an LLM.
# Some fields may not be supported by all providers, it's up to the model plugin to interpret them.

@dataclass
class llmConfig:
    provider: str
    model: str
    reasoning_effort: str | None = None
    priority: str | None = None
    
    def __post_init__(self):
        # Validate that the provider exists
        valid_providers = ["OpenAI", "Fake"]
        if self.provider not in valid_providers:
            raise ValueError(f"Invalid provider '{self.provider}'. Must be one of: {', '.join(valid_providers)}")
