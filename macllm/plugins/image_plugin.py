import os
from .base import MacLLMPlugin

class ImagePlugin(MacLLMPlugin):
    def __init__(self, macllm):
        self.macllm = macllm
        self.tmp_image = "/tmp/macllm.png"
    
    def get_prefixes(self) -> list[str]:
        return ["@selection", "@window"]
    
    def _capture_screen(self):
        """Capture a screen selection."""
        # Delete the temp image if it exists
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i /tmp/macllm.png")
        return self.tmp_image

    def _capture_window(self):
        """Capture the active window."""
        # Delete the temp image if it exists
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i -Jwindow /tmp/macllm.png")
        return self.tmp_image
    
    def expand(self, word: str, request) -> None:
        if word == "@selection":
            self._capture_screen()
            self.macllm.debug_log(f'Sending image size {os.path.getsize(self.tmp_image)} to LLM.')
        elif word == "@window":
            self._capture_window()
            self.macllm.debug_log(f'Sending image size {os.path.getsize(self.tmp_image)} to LLM.')
        
        request.expanded_prompt = request.expanded_prompt.replace(word, " the image ")
        request.needs_image = True 