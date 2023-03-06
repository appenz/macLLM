# macLLM - Use ChatGPT with your Clipboard

This is a super simple python script that does the following:
- It watches your clipboard for a trigger (default is the double at symbol, i.e. "@@")
- If your clipboard starts with this trigger, it sends the clipboard to a model (e.g. ChatGPT) and pastes the result back into the clipboard

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

You can add your own shortcuts for prompts in the shortcuts.py file.

## License

Apache 2.0

## Running

Install openapi python stubs:
> pip3 install openapi

Get an API key from OpenAI and either store it in the environment variable OPENAI_API_KEY or alternatively set it in a file apikey.py (i.e. apikey="...").

Run it:
> python3 macLLM.py

If you run it in a terminal, it will show the results of your query which can be useful.
