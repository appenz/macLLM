#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken fromthe environment variable OPENAI_API_KEY
# or imported from the file apikey.py
#

import os
import subprocess
import openai
import time

from macllm.shortcuts import ShortCut
from macllm.ui import MacLLMUI

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
    model = "gpt-4o"
    temperature = 0.0

    def __init__(self, model=LLM.model, temperature=0.0):
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


class MacLLM:

    # Watch the clipboard for the trigger string "@@" and if you find it run through GPT
    # and write the result back to the clipboard

    def show_instructions(self):
        print()
        print(f'To use this tool:')
        print(f'1. Copy text that starts with "@@" (no quotes!) to the clipboard')
        print(f'2. Wait a second while this text is being sent to {LLM.model} and the result is written back to the clipboard.')
        print(f'3. Paste.')
        print()

    def __init__(self):
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.clipboard = Clipboard()
        self.llm = LLM()
        self.req = 0

    def main_loop(self):
        txt = self.clipboard.get().decode()
        if txt.startswith("@@"):
            self.req = self.req+1
            print(color.RED + f'Request #{self.req} : ', txt, color.END)
            if ShortCut.checkShortcuts(txt):
                txt = ShortCut.checkShortcuts(txt).generate(txt)
            else:
                txt = txt[2:].strip()
            out = self.llm.generate(txt).strip()
            print(out)
            print()
            self.clipboard.set(out.encode())

def main():
    m = MacLLM()
    m.show_instructions()
    # Create a clipboard object
    

if __name__ == "__main__":
    main()

