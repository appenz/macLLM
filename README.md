# macLLM - Use ChatGPT with your Clipboard

This is a super simple python script that does the following:
- It watches your clipboard for a trigger (default is the double at symbol, i.e. "@@")
- If your clipboard starts with this trigger, it sends the clipboard to a model (e.g. ChatGPT) and pastes the result back into the clipboard

## Installation

macLLM now uses the Poetry package manager, make sure you have it installed first (https://python-poetry.org/).
Then, install macLLM with:

> poetry install

Your OpenAI API key should be configured in the environment variable OPENAI_API_KEY. Poetry will also automatically read it if it is specified in a .env file. Format is:

> OPENAI_API_KEY="your_api_key"

Now you can run macllm it with:

> poetry run macllm

Poetry should take care of all the dependencies, you don't need to install anything else.

## How do you use this?

For example, let's assume you forgot the capital of France. You write:

> @@capital of france?

You mark this text, copy (i.e. Apple-C), wait 1-2 seconds, and paste (Apple-P). 

> Paris

Or you want to tell someon in German that ControlNet is underrated, you would write:

> @@translate german: ControlNet is an AI technology that is really underrated

Copy, paste:

> ControlNet ist eine AI-Technologie, die wirklich unterschätzt wird.

And of course you can also use this to summarize text, expand text to bullet points or anything else ChatGPT can do.

## Shortcuts

Shortcuts are shorthand for specifc prompts. So for example "@@fix" is a prompt that corrects spelling or "@@tr-es" is short for translate to Spanish. You use them in text like this:

>@@fix My Canaidian Mooose is Braun.

This gets internally expanded to:

>@@Correct any spelling or grammar mistakes in the following text: My Canaidian Mooose is Braun.

Which GPT will correct to:

> My Canadian Moose is Brown.

You can add your own shortcuts for prompts in the shortcuts.py file. Currently supported shortcuts are:

### Supported Shortcuts
- `@@exp-email`: Write an extremely concise and friendly email based on bullet points.
- `@@exp`: Expand the text using sophisticated and concise language.
- `@@fix-de`: Correct spelling and grammar mistakes in the following German text.
- `@@fix-fr`: Correct spelling and grammar mistakes in the following French text.
- `@@fix`: Correct spelling and grammar mistakes in the following text.
- `@@rewrite`: Rewrite the text to be extremely concise while keeping the same meaning.
- `@@tr-de`: Translate the text from English to German.
- `@@tr-fr`: Translate the text from English to French.
- `@@tr-es`: Translate the text from English to Spanish.
- `@@emoji`: Pick a relevant emoji for the text and reply with only that emoji.


## License

Apache 2.0

