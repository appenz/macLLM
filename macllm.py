#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2023 Guido Appenzeller
#
# OpenAI API Key is taken fromthe environment variable OPENAI_API_KEY
# or imported from the file apikey.py
#

import os
import subprocess
import openai
import time

from shortcuts import ShortCut

class color:
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

class Clipboard:

    def get(self):
        p = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
        r = p.wait()
        data = p.stdout.read()
        return data

    def set(self,data):
        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        p.stdin.write(data)
        p.stdin.close()
        r = p.wait()

class LLM:

    client = None

    def __init__(self, model="gpt-4-1106-preview", temperature=0.0):
        self.model = model
        self.temperature = temperature
        self.client = openai.OpenAI(api_key=openai.api_key)

    def generate(self, text):
        c = self.client.chat.completions.create(
          model=self.model,
          messages = [
            {"role": "user", "content": str(text)},
          ],
          temperature = self.temperature,
        )
        return c.choices[0].message.content

# Get API Key from environment variable or from file
# e.g. export OPENAI_API_KEY="copy pasted from https://platform.openai.com/account/api-keys"
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    import apikey
    openai.api_key = apikey.apikey

# Create a clipboard object
clipboard = Clipboard()
llm = LLM()
req = 0

# Watch the clipboard for the trigger string "@@" and if you find it run through GPT
# and write the result back to the clipboard

print()
print('To use this tool:')
print('1. Copy text that starts with "@@" (no quotes!) to the clipboard')
print('2. Wait a second while this text is being sent to GPT-3 and the result is written back to the clipboard.')
print('3. Paste.')
print()

while True:
    txt = clipboard.get().decode()

    if txt.startswith("@@"):
        req = req+1
        print(color.RED + f'Request #{req} : ', txt, color.END)
        if ShortCut.checkShortcuts(txt):
            txt = ShortCut.checkShortcuts(txt).generate(txt)
        else:
            txt = txt[2:].strip()
        out = llm.generate(txt).strip()
        print(out)
        print()
        clipboard.set(out.encode())
    # wait 1 second
    time.sleep(1)

# @@Capital of France?
