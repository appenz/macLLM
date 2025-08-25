from .base import TagPlugin


class SpeedTag(TagPlugin):
    def get_prefixes(self):
        return ["@fast", "@slow", "@think"]
    
    def expand(self, tag, conversation, request):
        if tag == "@fast":
            request.speed_level = "fast"
        elif tag in ["@slow", "@think"]:
            request.speed_level = "slow"
        return ""  # Remove tag from prompt
