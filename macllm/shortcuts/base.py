from core.user_request import UserRequest

class ShortcutPlugin:
    """Base class for macLLM shortcuts that handle @ tag expansions."""
    
    def get_prefixes(self) -> list[str]:
        """Return list of prefixes this plugin handles."""
        pass
    
    def expand(self, word: str, request: UserRequest) -> None:
        """
        Expand a word that matches one of this plugin's prefixes.
        Modifies the request object directly instead of returning values.
        """
        pass 