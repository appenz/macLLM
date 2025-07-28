from macllm.core.model_connector import ModelConnector


class FakeConnector(ModelConnector):
    """Minimal connector that records prompts for tests."""

    def __init__(self, model: str = "fake-model"):
        super().__init__(model)
        self.last_text = None
        self.last_image_path = None

    def generate(self, text: str) -> str:  # noqa: D401
        self.last_text = text
        return "MOCK_RESPONSE"

    def generate_with_image(self, text: str, image_path: str) -> str:  # noqa: D401
        self.last_text = text
        self.last_image_path = image_path
        return "MOCK_RESPONSE"

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def get_context_blocks(self):  # pragma: no cover
        """Return a dict of {context_name: context_contents} parsed from the
        *last_text* prompt.

        The prompt built by :pymeth:`macllm.macllm.MacLLM.handle_instructions`
        contains blocks formatted like::

            --- contents:NAME ---
            ...
            --- end contents:NAME ---

        This helper extracts all such blocks so that tests can make direct
        assertions on them without re-implementing the parsing logic.
        """

        if not self.last_text:
            return {}

        import re

        pattern = re.compile(
            r"--- contents:(?P<name>[^\s]+) ---\n(?P<content>.*?)\n--- end contents:\1 ---",
            re.DOTALL,
        )

        return {m.group("name"): m.group("content") for m in pattern.finditer(self.last_text)} 