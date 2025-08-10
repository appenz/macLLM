# MacLLM Overview

MacLLM is a tool that helps a user to effectively use LLMs for working on macOS.

A user enters a request (e.g. "What is 1+1?") and MacLLM replies with a result (e.g. "2").
- A collection of requests/responses are called a **Conversation**.
- A user can provide context, e.g. a file or data in the clipboard. Context is for the entire conversation.
- The collection of all Conversations is called the **ChatHistory**.
- A **Request** is an ephemeral object that contains all the data that needs to be sent to the LLM, including context.

## Code Structure

- **MacLLM** is the base class that implements the tool (`macllm.py`)
    - The **ChatHistory**, **Conversations** and **Requests** are defined in (`chat_history.py`) 
- **MacLLMUI** is the Cocoa UI for MacLLM. All UI macOS UI code is in `ui` 
    - Main parts are the input area (bottom), main text area showing the conversation (middle) and the icon bar at thet top.
- **Core building blocks** are in the `core/` subdirectory
- **Plugins** that add additional `@` tags (e.g. `@clipboard`, file completion) are in the `tags` directory
- **Connectors** to LLMs and other models are in the `models/` directory

The code will only ever run on macOS. NEVER write dummy code or stub out code to make it run in other environments.

# UI Layout

The macLLM window has 3 main parts:
- A top bar with the icon. It shows context for this conversation and statistics
- The main conversation text area, it shows the conversation history
- The input area at the bottom