# MacLLM Overview

MacLLM is a tool that helps a user to effectively use LLMs for working on macOS.
It is written in Python with a UI in macOS Cocoa via the PyObjC bridge.

A user enters a request (e.g. "What is 1+1?") and MacLLM replies with a result (e.g. "2").
- A collection of requests/responses are called a **Conversation**.
- A user can provide context, e.g. a file or data in the clipboard. Context is embedded in the user message where it was referenced.
- The collection of all Conversations is called the **ConversationHistory**.
- A **UserRequest** is an ephemeral object that processes @tags and builds the message to send to the LLM.

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
    - `llm_service.py`: LLM integration via LiteLLM library
    - `agent_service.py`: Agent factory (`create_agent()`) and step callbacks
    - `agent_status.py`: `AgentStatusManager` for live plan/tool-call display
    - `memory.py`: Conversation persistence (save/load/clear)
- **Tags** (`tags/`): Plugin system for @tag and /command expansion (e.g. `@clipboard`, `@file`, `/fast`, `@agent:`)
- **Agents** (`agents/`): Agent architecture built on smolagents (see `specs/agents.md`)
- **Tools** (`tools/`): Agent tool implementations (`web_search`, `search_files`, `read_full_file`, `file_append`, `file_create`, `get_current_time`)
- **Markdown** (`markdown/`): Markdown-to-`NSAttributedString` rendering for assistant messages

## LLM Integration

MacLLM uses [LiteLLM](https://docs.litellm.ai/) as a unified interface to multiple LLM providers. This allows switching between providers (OpenAI, Anthropic, local models, etc.) without code changes.

Speed commands (`/fast`, `/slow`, `/think`) map to specific LiteLLM model strings configured in `llm_service.py`.

See `specs/history.md` for details on the message structure.

## Platform

The code will only ever run on macOS. NEVER write dummy code or stub out code to make it run in other environments.

## Running and testing

MacLLM is run and tested via make:
- ``make run`` to run the program normally
- ``make test`` to run local only tests (i.e. not using online services)
- ``make test-external`` to run tests that use models online
