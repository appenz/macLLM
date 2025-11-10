# MacLLM Overview

MacLLM is a tool that helps a user to effectively use LLMs for working on macOS.
It is written in Python with a UI in macOS Cocoa via the PyObjC bridge.

A user enters a request (e.g. "What is 1+1?") and MacLLM replies with a result (e.g. "2").
- A collection of requests/responses are called a **Conversation**.
- A user can provide context, e.g. a file or data in the clipboard. Context is for the entire conversation.
- The collection of all Conversations is called the **ConversationHistory**.
- A **UserRequest** is an ephemeral object that processes @tags and contains all data sent to the LLM.

## Code Structure

- **MacLLM** (`macllm.py`) - Main class that coordinates requests, conversation history, and UI
- **MacLLMUI** (`ui/core.py`) - Cocoa UI implementation with three main areas:
    - Top bar: icon, context pills, model/token stats
    - Main text area: scrollable conversation history
    - Input field: text entry with @tag autocomplete
- **Core** (`core/`):
    - `chat_history.py`: `ConversationHistory` (collection) and `Conversation` (individual)
    - `user_request.py`: `UserRequest` class for processing @tags
    - `shortcuts.py`: Slash-based user-defined shortcuts loaded from TOML config files (e.g. `/travelinfo`)
    - `model_connector.py`: Base connector interface
- **Tags** (`tags/`): Plugin system for @tag expansion (e.g. `@clipboard`, `@file`, `@speed`)
- **Models** (`models/`): LLM connectors (`openai_connector.py`, `fake_connector.py` for tests)

The code will only ever run on macOS. NEVER write dummy code or stub out code to make it run in other environments.