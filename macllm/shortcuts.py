#
# Shortcuts for LLM expansion
# (c) in 2023 Guido Appenzeller
#

promptShortcuts = [
    ["@exp-email", "Write an email based on the following bullet points. Your email should be extremely concise. Avoid unnecessary words. Be friendly, enthusiastic and high energy. Your expanded email should not change the meaning from the bullet points.\n ---\n"],
    ["@exp", "Expand the following into paragraphs of text. The output should not consist of bullet points any more. Use extremely concise language. Your style should be sophisticated like The Economist or the Wall Street Journal. It's fine to use complex technical terms if needed. Avoid any unecessary words. Do not change the meaning of the text\n ---\n"],
    ["@fix-de", "Korrigiere alle Rechtschreib- und Grammatikfehler im folgenden deutschen Text:"],
    ["@fix-fr", "Corrigez toutes les fautes d'orthographe et de grammaire dans le texte en langue française suivant:"],
    ["@fix", "Correct any spelling or grammar mistakes in the following text:"],
    ["@rewrite", "Rewrite the following text but keep the same meaning and be extremely concise.\n---\n"],
    ["@tr-de", "Translate the following text from English to German.\n---\n"],
    ["@tr-fr", "Translate the following text from English to French.\n---\n"],
    ["@tr-es", "Translate the following text from English to Spanish.\n---\n"],
    ["@emojis", "Pick a sequence of up to 5 emojis that are relevant to the following text. Reply only with the emojis, i.e. up to five characters. Do not exmplain your choice or write any other text.\n---\n"],
    ["@emoji", "Pick an emoji that is relevant to the following text. Reply only with that emoji, i.e. a single character. Do not exmplain your choice or write any other text.\n---\n"],
    ["@linkedin", "List the job experience of this person, use one bullet point per job."],
    ["@slide", "Summarize the contents of this slide in a few bullet points. Each bullet point should fit on a single line."],
    ["@transcribe", "Precisely transcribe this image. Do not explain it. Reply only with the transcript and nothing else."],
]

# Class that handles shortcuts and the actions to be taken

class ShortCut:
    shortcuts = []

    # Class method to expand all shortcuts in the text

    @classmethod
    def expandAll(cls, text):
        for s in cls.shortcuts:
            text = s.expand(text)
        return text

    def __init__(self, trigger, prompt):
        self.trigger = trigger
        self.prompt = prompt
        self.shortcuts.append(self)

    # Find all occurrences of the trigger in the text and expand them
    def expand(self, text):
        return text.replace(self.trigger, self.prompt)

# Initialize the shortcuts
for p in promptShortcuts:
    ShortCut(p[0], p[1])
    