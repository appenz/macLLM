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

from shortcuts import ShortCut
from ui import MacLLMUI

from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, cmdKey, controlKey

import openai

macLLM = None

start_token = "!!"
alias_token = "@"

# Class defining ANSI color codes for terminal output
class color:
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

@quickHotKey(virtualKey=kVK_ANSI_A, modifierMask=mask(cmdKey, controlKey))
def handler():
    global macLLM
    macLLM.ui.hotkey_pressed()

def load_env():
    try:
        with open('.env', 'r') as env_file:
            for line in env_file:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error while parsing .env file: {str(e)}")

class LLM:

    client = None
    model = "gpt-4o"
    temperature = 0.0

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

        print(f'Sending to gpt-4o')
        print(headers)
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

    def show_instructions(self):
        print()
        print(f'Welcome to macLLM. To use this tool:')
        print(f'1. Copy text that starts with "@@" (no quotes!) to the clipboard')
        print(f'2. Wait a second while this text is being sent to {LLM.model} and the result is written back to the clipboard.')
        print(f'3. Paste.')
        print()

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

    def __init__(self):
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.llm = LLM()
        self.req = 0

        self.ui.clipboardCallback = self.clipboard_changed

    def handle_instructions(self, text):
        self.req = self.req+1
        print(color.RED + f'Request #{self.req} : ', text, color.END)
        txt = ShortCut.expandAll(text)

        # Check if we have a @screen tag that requires screen capture
        if "@selection" in txt:
            self.capture_screen()
            txt = txt.replace("@selection", " the image ").strip()
            out = self.llm.generate_with_image(txt, self.tmp_image)
        elif "@window" in txt:
            self.capture_window()
            txt = txt.replace("@window", " the image ").strip()
            out = self.llm.generate_with_image(txt, self.tmp_image)
        else:                        
            out = self.llm.generate(txt).strip()
        print(out)
        print()
        self.ui.write_clipboard(out)    
        return out
        
    def clipboard_changed(self):
        txt = self.ui.read_clipboard()

        if txt.startswith(start_token):
            self.handle_instructions(txt[len(start_token):])


def main():
    global macLLM
    load_env()
    macLLM = MacLLM()
    macLLM.show_instructions()
    macLLM.ui.start()

# @@Capital of France?
# @@capture Transcribe the text in this image.

if __name__ == "__main__":
    main()

