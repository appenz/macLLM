#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken fromthe environment variable OPENAI_API_KEY
# or imported from the file apikey.py
#

import base64
import requests
import os
import argparse

import openai

from shortcuts import ShortCut
from ui import MacLLMUI
from webtools import retrieve_url

# Note: quickmachotkey needs to be imported after the ui.py file is imported. No idea why.
from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey


macLLM = None

start_token = "@@"
alias_token = "@"

# Class defining ANSI color codes for terminal output
class color:
   RED = '\033[91m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   BLUE = '\033[94m'
   BOLD = '\033[1m'
   GREY = '\033[90m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

# Define the hotkey: option-space
@quickHotKey(virtualKey=kVK_Space, modifierMask=mask(optionKey))
# Ctrl-command-a instead
#@quickHotKey(virtualKey=kVK_ANSI_A, modifierMask=mask(cmdKey, controlKey))

def handler():
    global macLLM
    macLLM.ui.hotkey_pressed()
        
class LLM:

    client = None
    model = "gpt-4o"
    temperature = 0.0
    context_limit = 10000

    def __init__(self, model=model, temperature=0.0):
        self.model = model
        self.temperature = temperature
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.openai_api_key is None:
            raise Exception("OPENAI_API_KEY not found in environment variables")
        self.client = openai.OpenAI(api_key=self.openai_api_key)

    def generate(self, text):
        c = self.client.chat.completions.create(
          model=self.model,
          messages = [
            {"role": "user", "content": str(text)},
          ],
          temperature = self.temperature,
        )
        return c.choices[0].message.content
    
    # Function to encode the image
    def encode_image(self,image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_with_image(self, text, image_path):

        # Getting the base64 string
        base64_image = self.encode_image(image_path)
        if base64_image is None:
            print(f'Image encoding failed.')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }

        payload = {
        "model": "gpt-4o",
        "messages": [
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": f"{text}"
                },
                {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
                }
            ]
            }
        ],
        "max_tokens": 1000
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        # Extract the content from the response
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                generated_text = response_data['choices'][0]['message']['content']
                print(f'Generated Text: {generated_text}')
                return generated_text
            else:
                print('No generated content found.')
                return None
        else:
            print(f'Failed to generate content. Status Code: {response.status_code}')
            print(response.json())
            return None


class MacLLM:

    # Watch the clipboard for the trigger string "@@" and if you find it run through GPT
    # and write the result back to the clipboard

    tmp_image = "/tmp/macllm.png"
    version = "0.1.0"

    def show_instructions(self):
        print(f'Hotkey for quick entry window is ⌥-space (option-space)')
        print(f'To use via the clipboard, copy text starting with "@@"')

    def capture_screen(self):
        # Delete the temp image if it exists
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i /tmp/macllm.png")
        return "/tmp/macllm.png"

    def capture_window(self):
        # Delete the temp image if it exists
        if os.path.exists(self.tmp_image):
            os.remove(self.tmp_image)
        os.system("screencapture -x -i -Jwindow /tmp/macllm.png")
        return "/tmp/macllm.png"

    def __init__(self, model="gpt-4o", debug=False):
        self.debug = debug
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.llm = LLM(model=model)
        self.req = 0

        self.ui.clipboardCallback = self.clipboard_changed

    def handle_instructions(self, text):
        self.req = self.req+1
        text = text.strip()
        if self.debug:
            print(color.BOLD + f'Request #{self.req} : ', color.END, text, )
        txt = ShortCut.expandAll(text)
        context = ""
        error = None
        
        # Expand text tags (clipboard, file, URL, etc.)
        context = ""
        if "@clipboard" in txt:
            txt = txt.replace("@clipboard", " CLIPBOARD_CONTENTS ")
            context += "\n--- CLIPBOARD_CONTENTS START ---\n"
            context += self.ui.read_clipboard()
            context += "\n--- CLIPBOARD_CONTENTS END ---\n\n"

        # Expand URLs
        if "@http://" in txt or "@https://" in txt:
            words = txt.split()
            for word in words:
                if word.startswith("@http://") or word.startswith("@https://"):
                    try:
                        actual_url = word[1:]  # Remove the @ prefix
                        content = retrieve_url(actual_url)
                        if len(content) > self.llm.context_limit:
                            content = content[:self.llm.context_limit] + "\n[Content truncated...]"
                        txt = txt.replace(word, f" URL_CONTENTS ")
                        context += f"\n--- URL_CONTENTS START ---\n"
                        context += content
                        context += "\n--- URL_CONTENTS END ---\n\n"
                    except Exception as e:
                        error = txt.replace(word, f"\n[Error retrieving {actual_url}: {str(e)}]\n")
                        txt = ""

        # Handle cases where we have to send an image to the LLM
        if "@selection" in txt or "@window" in txt:
            if "@selection" in txt:
                self.capture_screen()
                txt = txt.replace("@selection", " the image ").strip()
            elif "@window" in txt:
                self.capture_window()
                txt = txt.replace("@window", " the image ").strip()
            if self.debug:
                print(color.GREY + f'Sending image size {os.path.getsize(self.tmp_image)} to LLM. ', txt, color.END)
            out = self.llm.generate_with_image(txt+context, self.tmp_image)
        else:                        
            # No image, just send the text to the LLM
            if self.debug:
                print(color.GREY + f'Sending text length {len(txt)} to {self.llm.model}. ', color.END)
            out = self.llm.generate(txt+context).strip()
            
        if self.debug:
            if error:
                print(color.RED + error + color.END)
            print(f'Output: ', out.strip())
            print("\n")

        return out
        
    def clipboard_changed(self):
        txt = self.ui.read_clipboard()

        if txt.startswith(start_token):
            out = self.handle_instructions(txt[len(start_token):])
            self.ui.write_clipboard(out)    


def main():
    global macLLM

    parser = argparse.ArgumentParser(description="macLLM - a simple LLM tool for the macOS clipboard")
    parser.add_argument("--model", type=str, default="gpt-4o", help="The LLM model to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.debug:
        debug_str = color.RED + "Debug mode is enabled" + f" (v {MacLLM.version})" + color.END
        print(f"Welcome to macLLM. {debug_str}")

    macLLM = MacLLM(model=args.model, debug=args.debug)
    macLLM.show_instructions()
    macLLM.ui.start()

if __name__ == "__main__":
    main()

