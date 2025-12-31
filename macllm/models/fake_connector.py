import re

class FakeConnector:
    """Minimal connector that records prompts for tests."""

    last_text = None
    last_image_path = None

    @classmethod
    def _generate(cls, text: str, model: str, image_path: str = None) -> tuple[str, dict]:
        cls.last_text = text
        cls.last_image_path = image_path
        metadata = {
            'provider': 'Fake',
            'model': model,
            'tokens': 0
        }
        return "MOCK_RESPONSE", metadata

    @classmethod
    def generate(cls, text: str, speed: str = "normal", image_path: str = None, debug_logger=None) -> tuple[str, dict]:
        speed = speed.lower()
        if speed == "fast":
            model = "fake-model-fast"
        elif speed == "slow":
            model = "fake-model-slow"
        else:
            model = "fake-model"
        return cls._generate(text, model, image_path)

    @classmethod
    def get_context_blocks(cls):
        """Return a dict of {context_name: context_contents} parsed from the
        *last_text* prompt.

        The prompt built by :pymeth:`macllm.macllm.MacLLM.handle_instructions`
        contains blocks formatted like::

            --- context:NAME ---
            ...
            --- end context:NAME ---

        This helper extracts all such blocks so that tests can make direct
        assertions on them without re-implementing the parsing logic.
        """

        if not cls.last_text:
            return {}

        pattern = re.compile(
            r"--- context:(?P<name>[^\s]+) ---\n(?P<content>.*?)\n--- end context:\1 ---",
            re.DOTALL,
        )

        return {m.group("name"): m.group("content") for m in pattern.finditer(cls.last_text)}
