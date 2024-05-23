#
# Shortcuts for LLM expansion
# (c) in 2023 Guido Appenzeller
#

promptShortcuts = [
    ["@@exp-email", "Write an email based on the following bullet points. Your email should be extremely concise. Avoid unnecessary words. Be friendly, enthusiastic and high energy. Your expanded email should not change the meaning from the bullet points.\n ---\n"],
    ["@@exp", "Expand the following text. Use extremely concise language. Your style should be sophisticated like The Economist or the Wall Street Journal. It's fine to use complex technical terms if needed. Avoid any unecessary words. Do not change the meaning of the text\n ---\n"],
    ["@@fix-de", "Bitte korrigiere alle Rechtschreib- und Grammatikfehler im folgenden deutschen Text:"],
    ["@@fix-fr", "Corrigez toutes les fautes d'orthographe et de grammaire dans le texte en langue française suivant:"],
    ["@@fix", "Correct any spelling or grammar mistakes in the following text:"],
    ["@@rewrite", "Rewrite the following text but keep the same meaning and be extremely concise.\n---\n"],
    ["@@tr-de", "Translate the following text from English to German.\n---\n"],
    ["@@tr-fr", "Translate the following text from English to French.\n---\n"],
    ["@@tr-es", "Translate the following text from English to Spanish.\n---\n"],
    ["@@emojis", "Pick a sequence of up to 5 emojis that are relevant to the following text. Reply only with the emojis, i.e. up to five characters. Do not exmplain your choice or write any other text.\n---\n"],
    ["@@emoji", "Pick an emoji that is relevant to the following text. Reply only with that emoji, i.e. a single character. Do not exmplain your choice or write any other text.\n---\n"],
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
    