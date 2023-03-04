# macLLM - Use Large Language Models (e.g. ChatGPT) with your Clipboard on macOS

This is a super simple python script that does the following:
- It watches your clipboard for a trigger (default is the double at symbol, i.e. "@@")
- If your clipboard starts with this trigger, it sends the clipboard to a model (e.g. ChatGPT) and pastes the result back into the clipboard

## How do you use this?

Say you want to tell someon in German that ControlNet is underrated, you would write:

> @@ Translate to German: ControlNet is an AI technology that is really underrated

You mark this text, copy (i.e. Apple-C), wait 1-2 seconds, and paste (Apple-P). The result is:

> ControlNet ist eine KI-Technologie, die wirklich unterbewertet wird.

And of course you can also use this to summarize text, expand text to bullet points, check if something is factually correct etc.

## License

Apache 2.0

## Running

Install openapi python stubs:
> pip3 install openapi

Get an API key from OpenAPI and either store it in the environment variable OPENAI_API_KEY or alternatively set it in a file apikey.py (i.e. apikey="...").

Run it:
> python3 macLLM.py

If you run it in a terminal, it will show the results of your query which can be useful.
