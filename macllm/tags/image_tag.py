import os
from .base import TagPlugin

class ImageTag(TagPlugin):
    """Expands @selection or @window tags by capturing a screenshot and adding it as binary context."""

    def __init__(self, macllm):
        super().__init__(macllm)
        self.tmp_image = "/tmp/macllm.png"

    def get_prefixes(self):
        return ["@selection", "@window"]

    def expand(self, tag: str, conversation, request):
        # Capture the image to temporary file and load bytes
        if tag == "@selection":
            self._capture_screen()
        elif tag == "@window":
            self._capture_window()
        else:
            return tag  # fallback

        try:
            from PIL import Image
            img = Image.open(self.tmp_image)
            img.load()
        except (FileNotFoundError, Exception):
            return tag

        request.images.append(img)
        conversation.add_context(
            "Screenshot",
            tag,
            "image",
            "[image]",
        )
        return "the image"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _capture_screen(self):
        # Delete any previous image then call screencapture
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i /tmp/macllm.png")

    def _capture_window(self):
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i -Jwindow /tmp/macllm.png") 