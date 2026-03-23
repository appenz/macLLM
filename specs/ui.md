# UI Architecture

## Overview

The UI is a native Cocoa interface implemented through PyObjC under `macllm/ui/`.

The UI layer is responsible for:

- application and window lifecycle
- rendering conversation state
- presenting context, model, and status metadata
- handling text input, pills, and autocomplete
- coordinating history browsing

The main coordinator is `MacLLMUI` in `macllm/ui/core.py`.

## Structure

The UI is split into a few focused parts:

- `MacLLMUI` coordinates window creation, layout, updates, and high-level user actions
- `TopBarHandler` renders the top metadata strip, including context pills and model/token information
- `MainTextHandler` renders the conversation view, assistant markdown, and live agent status
- `InputFieldHandler` and `InputFieldDelegate` manage text editing, pills, commands, and autocomplete
- `AutocompleteController` provides token suggestions and selection behavior
- `HistoryBrowseDelegate` handles keyboard-driven navigation through prior messages

This keeps rendering, editing, and navigation behavior separate while still allowing `MacLLMUI` to own the whole window.

## Update Model

The UI is updated from both direct user actions and background agent activity.

`MacLLMUI.request_update()` is the key boundary between background work and Cocoa rendering.
If the caller is already on the main thread, the window is updated immediately. Otherwise the update is marshaled back to the main thread before any UI mutation happens.

This is an important design choice in the app: the agent runtime may run on background threads, but the UI remains single-threaded and Cocoa-safe.

## Conversation Rendering

The main conversation view is a text-based rendering pipeline.

- user messages are rendered as plain text with pills for recognized tags and commands
- assistant messages are rendered through the markdown subsystem
- live agent status is appended at the bottom while an agent run is active

The UI reads displayable messages from conversation state rather than reconstructing the request from the expanded prompt.

## Input Model

The input field is more than a plain text box.

It supports:

- token-aware autocomplete for `@` and `/`
- insertion of pills that retain a raw underlying token
- command-key shortcuts for speed selection and other actions
- Shift-Enter for literal newlines
- Enter for submission

The key design choice is that displayed text and inserted raw token text can differ. The user sees a short pill label, but the input field retains the underlying token needed for later parsing and expansion.

## Top Bar and Status

The top bar is the compact summary of the current conversation state.

It shows:

- branding and window identity
- recent context pills
- model and token metadata

Long-running agent activity is not shown in the top bar. It is rendered in the conversation view by `MainTextHandler`, using structured state from `AgentStatusManager`.

## History Browsing

History browsing is a separate interaction mode layered on top of the conversation view.

When active, the conversation text view becomes the keyboard target. The user can move through prior messages, copy them, or insert one back into the input field. This is handled by a dedicated delegate rather than by the normal input delegate.

## Layout Model

The window layout is computed dynamically from rendered content height.

The UI uses:

- a fixed-width quick-entry window
- a top bar
- a scrollable main text area
- a multi-line input area

Window height grows with content up to a screen-relative maximum, which keeps the interface compact for short exchanges but usable for long ones.
