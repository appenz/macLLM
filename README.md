# macLLM - Fast LLM Desktop Utility for macOS

macLLM is a utility that makes it easy to work with LLMs from the macOS desktop. It is launched
via a hotkey and can do things like:
* Send a prompt to an LLM, e.g. "What state is Kansas City in?"
* Translate or summarize text, e.g. "Translate the @clipboard to Spanish"
* Look at desktop windows, e.g. "Write a short biography based on this LinkedIn @window"
* Find good emojis for a specific topic, e.g. "@emojis: diving in hawaii"
* Work with URLs, e.g. "summarize @https://github.com/appenz/macLLM/edit/main/README.md"
* Work with files, e.g. "find the ship date in @~/Documents/Notes/team-meeting.md"

macLLM is open source (Apache 2.0) and designed to be easily extensible with your own workflows.
Here is a short demo video (with sound) of some of the capabilities.

https://github.com/user-attachments/assets/391b85da-689e-4b49-b449-dd3593ea512c

## Installation

macLLM uses the uv package manager, make sure you have it installed first (https://github.com/astral-sh/uv). 

Your OpenAI API key should be configured in the environment variable OPENAI_API_KEY.

> OPENAI_API_KEY="your_api_key"

Now you can run macllm it with:

> uv run macllm/macllm.py

uv should take care of all the dependencies.

## Basic Usage

Press the hotkey. By default, it is option-space (⌥-space) but it can be easily remapped. 
A small window will appear in the center of the screen and you can start typing a query to the LLM.
For example:

> Capital of france?

After a second or so you should ge the answer "Paris". You can now do a few things:
1. Hit escape to close the window. Pressing the hotkey again will close it as well.
2. You can copy the text to the clipboard by pressing Command-C (⌘-C). This will also close the macLLM window.
3. Type a new query into the text box.

## Referencing external data

macLLM understands a number of external data sources:
* @clipboard is the current clipboard content
* @window is any desktop window. You can select it after entering the query with your mouse.
* @selection allows you to select any area on the screen.
* @<filename> is any file in macOS. The path has to start with "/" or "~"
* @<url> for an http url. It has to start with "http" or "https"

The data can be referenced in the query, e.g. "translate @clipboard into French" or "summarize the slide @window".

## Shortcuts

Shortcuts are shorthand for specifc prompts. They always start with the @ symbol. So for example "@fix" is a prompt that corrects spelling or "#tr-es" is short for translate to Spanish. 

>@fix My Canaidian Mooose is Braun.

This gets internally expanded to:

>#Correct any spelling or grammar mistakes in the following text: My Canaidian Mooose is Braun.

Which GPT will correct to:

> My Canadian Moose is Brown.

You can add your own shortcuts in two ways:
1. In the shortcuts.py file for built-in shortcuts
2. In TOML config files in either:
   - App config directory: ./config/
   - User config directory: ~/.config/macllm/

Config files should use TOML format with a shortcuts table. Example:
```toml
shortcuts = [
  ["@exampleshortcut", "This is the expanded version of the exampleshortcut."],
  ["@hosts", "@/etc/hosts"],
]
```

## Example Shortcuts
- `#exp`: Expand the text using sophisticated and concise language.
- `#fix`: Correct spelling and grammar mistakes in the following text.
- `#fix-de`: Correct spelling and grammar mistakes in the following German text.
- `#rewrite`: Rewrite the text to be extremely concise while keeping the same meaning.
- `#tr-de`: Translate the text from English to German.
- `#emoji`: Pick a relevant emoji for the text and reply with only that emoji.
- `#emoji`: Pick a few relevant emojis for the text and reply with only those emojis.

## Using it via the clipboard

If the clipboard contains a text that starts with the trigger (default is "@@"), it will be sent to the LLM.
This can be useful if you want to use macLLM from withint an editor. Just type "@@" followed by instructions (e.g. "@@shorten this paragraph:"), hit copy (i.e. Apple-C), wait 1-2 seconds, and paste (Apple-P). 

## License

Apache 2.0


