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

    def __init__(self, model="gpt-3.5-turbo", temperature=0.0):
        self.model = model
        self.temperature = temperature

    def generate(self, text):
        c = openai.ChatCompletion.create(
          model=self.model,
          messages = [
            {"role": "user", "content": str(text)},
        ],
        )
        return c.choices[0].message.content

# Get API Key from environment variable or from file
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

while True:
    txt = clipboard.get().decode()

    if txt.startswith("@@"):
        req = req+1
        txt = txt[4:]
        out = llm.generate(txt)
        print(f'--- Request: {req} ----------------------------')
        print(llm.generate(txt))
        clipboard.set(out.encode())
    # wait 1 second
    time.sleep(1)
