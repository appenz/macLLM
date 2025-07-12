from .base import ShortcutPlugin

class FilePlugin(ShortcutPlugin):
    def get_prefixes(self) -> list[str]:
        return ["@/", "@~","@\"/", "@\"~"]
    
    def _read_file(self, filepath: str) -> str:
        """Read and validate a text file."""
        MAX_SIZE = 10 * 1024  # 10KB in bytes
        
        try:
            # Try to read file as text
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(MAX_SIZE)  # Only read up to MAX_SIZE bytes
                
                # Check for null bytes which indicate binary content
                if '\0' in content:
                    raise ValueError("File appears to be binary")
                    
                return content
                
        except UnicodeDecodeError:
            raise ValueError("File appears to be binary")
        except IOError as e:
            raise IOError(f"Failed to read file: {str(e)}")
    
    def expand(self, word: str, request) -> None:
        content = self._read_file(word[1:])
        request.expanded_prompt = request.expanded_prompt.replace(word, " FILE_CONTENTS ")
        request.context += f"\n--- FILE_CONTENTS START ---\n{content}\n--- FILE_CONTENTS END ---\n\n" 