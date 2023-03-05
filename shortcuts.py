#
# Shortcuts for LLM expansion
# (c) in 2023 Guido Appenzeller
#

promptShortcuts = [
    ["@@exp", "Expand the following text. Use concise language, an academic tone, avoid unecessary words:"],
    ["@@fix", "Correct any spelling or grammar mistakes in the following text:"],
    ["@@rewrite", "Rewrite the following text but keep the same meaning:"],
    ["@@tr-de", "Translate the following text from English to German:"],
    ["@@tr-fr", "Translate the following text from English to French:"],
    ["@@tr-es", "Translate the following text from English to Spanish:"],
]

# Class that handles shortcuts and the actions to be taken

class ShortCut:
    shortcuts = []

    def __init__(self, trigger, prompt):
        self.trigger = trigger
        self.prompt = prompt
        self.shortcuts.append(self)

    def generate(self, text):
        if not text.startswith(self.trigger):
            return False
        return self.prompt + text[len(self.trigger):]
    
    @classmethod
    def checkShortcuts(cls, text):
        for s in cls.shortcuts:
            if text.startswith(s.trigger):
                return s
        return None
    
for p in promptShortcuts:
    ShortCut(p[0], p[1])
    