# Context Overview

A conversation with the LLM can have a number of context items. A context item 
is added every time the user refers to an external source in the conversation 
or the model uses a tool to find relevant context. Once context is added to a 
conversation it is never removed.

Context is stored in the conversation object in chat_history.py, which has 
functions to add_context which picks a unique name for the context that 
from then on can be user to refer to it.

Context sent to the LLM for every subsequent query.

In the UI, context is shown in the top bar in a minaturized form.

When a new conversation is started, any previous context is ignored.

