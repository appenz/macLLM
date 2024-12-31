# macLLM - Use ChatGPT with your Clipboard

This is a super simple python script that does the following:
- It watches your clipboard for a trigger (default is the double at symbol, i.e. "@@")
- If your clipboard starts with this trigger, it sends the clipboard to a model (e.g. ChatGPT) and pastes the result back into the clipboard

## Installation

macLLM now uses the uv package manager, make sure you have it installed first (https://github.com/astral-sh/uv). 

Your OpenAI API key should be configured in the environment variable OPENAI_API_KEY.

> OPENAI_API_KEY="your_api_key"

Now you can run macllm it with:

> uv run macllm/macllm.py

uv should take care of all the dependencies, you don't need to install anything else.

## How do you use this?

Press the hotkey. By default, it is option-space but it can be easily remapped. 
A small icon will appear in the center of the screen and you can start typing a query to the LLM.
For example:

> Capital of france?

After a second or so you should ge the answer "Paris". You can now do a few things:
1. Hit escape to close the window. Pressing the hotkey again will close it as well.
2. You can copy the text to the clipboard by pressing Apple-C. This will also close the macLLM window.
3. Type a new query into the text box.

## Using it via the clipboard

If the clipboard contains a text that starts with the trigger (default is "@@"), it will be sent to the LLM.
This can be useful if you want to use macLLM from withint an editor. Just type "@@" followed by instructions (e.g. "@@shorten this paragraph:"),
hit copy (i.e. Apple-C), wait 1-2 seconds, and paste (Apple-P). 

Or you want to tell someon in German that ControlNet is underrated, you would write:

> @@translate german: ControlNet is an AI technology that is really underrated

Copy, paste:

> ControlNet ist eine AI-Technologie, die wirklich unterschätzt wird.

And of course you can also use this to summarize text, expand text to bullet points or anything else ChatGPT can do.

## Shortcuts

Shortcuts are shorthand for specifc prompts. So for example "#fix" is a prompt that corrects spelling or "#tr-es" is short for translate to Spanish. They can be used with both the hotkey (type "#fix" mediteranian") or with the clipboard (copy "@@ #fix mediteranian"). Some examples:

>#fix My Canaidian Mooose is Braun.

This gets internally expanded to:

>#Correct any spelling or grammar mistakes in the following text: My Canaidian Mooose is Braun.

Which GPT will correct to:

> My Canadian Moose is Brown.

You can add your own shortcuts for prompts in the shortcuts.py file. A list of shortcuts is below.

## Working with the desktop

There are special shortcuts that designate the entire screen (#screen), the current window (#window), or the current text selection (#selection). They are processed as images. So for example you can say:

> #selection Transcribe this slide

This will allow you to select an area of the screen, transcribe it, and paste the result back into the clipboard.

### Supported Shortcuts
- `#exp-email`: Write an extremely concise and friendly email based on bullet points.
- `#exp`: Expand the text using sophisticated and concise language.
- `#fix-de`: Correct spelling and grammar mistakes in the following German text.
- `#fix-fr`: Correct spelling and grammar mistakes in the following French text.
- `#fix`: Correct spelling and grammar mistakes in the following text.
- `#rewrite`: Rewrite the text to be extremely concise while keeping the same meaning.
- `#tr-de`: Translate the text from English to German.
- `#tr-fr`: Translate the text from English to French.
- `#tr-es`: Translate the text from English to Spanish.
- `#emoji`: Pick a relevant emoji for the text and reply with only that emoji.

### Supported Shortcuts for Desktop
- `#screen`: Process the entire screen as an image.
- `#window`: Process the current window as an image.
- `#selection`: Process the current text selection as an image.

## License

Apache 2.0


