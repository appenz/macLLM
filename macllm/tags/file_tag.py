import os
from pathlib import Path
from .base import TagPlugin

class FileTag(TagPlugin):
    """Expands @/path or @~/path by embedding file contents as context."""

    MAX_SIZE = 10 * 1024  # 10KB

    def get_prefixes(self) -> list[str]:
        return ["@/", "@~", "@\"/", "@\"~"]

    def expand(self, tag: str, conversation):
        # Determine the file path represented by *tag*
        path_spec = tag[1:]  # strip leading '@'
        # Remove possible surrounding quotes
        if path_spec.startswith('"') and path_spec.endswith('"'):
            path_spec = path_spec[1:-1]
        # Expand ~ to home
        if path_spec.startswith('~'):
            path_spec = os.path.expanduser(path_spec)

        try:
            content = self._read_file(path_spec)
        except Exception as e:
            # Log error in debug mode but still return the original tag so the user sees it
            if self.macllm.debug:
                self.macllm.debug_log(str(e), 2)
            return tag  # leave unmodified

        suggested_name = f"{Path(path_spec).name}"
        context_name = conversation.add_context(
            suggested_name,
            path_spec,
            "path",
            content,
        )
        return f"content:{context_name}" 

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_file(self, filepath: str) -> str:
        """Read a text file with validation, raising if it's binary or too large."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(self.MAX_SIZE)
            if '\0' in content:
                raise ValueError("File appears to be binary")
        return content 