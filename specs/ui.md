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

The UI is a pure renderer of conversation state. It reads from the active `Conversation` and renders. The only signal from the agent runtime to the UI is a generic repaint callback.

`MacLLMUI.request_update()` is the key boundary between background work and Cocoa rendering. If the caller is already on the main thread, the window is updated immediately. Otherwise the update is marshaled back to the main thread via `performSelectorOnMainThread` with `waitUntilDone_: False`, so agent threads never block on UI rendering.

Multiple conversations may have agents running simultaneously. Each agent thread fires the same repaint callback. The UI does not know which conversation triggered the update — it re-reads all state from the active conversation on every repaint. Background tab activity still triggers repaints (to update tab bar indicators) but does not affect the main content area.

## Conversation Rendering

The main conversation view is a text-based rendering pipeline. The conversation is the sole data source.

- user messages are rendered as plain text with pills for recognized tags and commands
- assistant messages are rendered through the markdown subsystem
- tool call progress is rendered from `agent.memory.steps` while an agent run is active
- pending shell approvals are rendered from `conversation.pending_approval`

The UI reads displayable messages from conversation state rather than reconstructing the request from the expanded prompt.

## Input Model

The input field is more than a plain text box.

It supports:

- token-aware autocomplete for `@` and `/`
- insertion of pills that retain a raw underlying token
- command-key shortcuts for speed selection and other actions
- Shift-Enter for literal newlines
- Enter for submission (enqueues if agent is running)
- Escape for explicit agent interrupt

When the user presses Enter while an agent is running in the active tab, the query is added to the conversation's query queue and displayed as a user message. The agent processes it after the current run finishes. Aborting is an explicit gesture (Escape), not the default behavior of Enter.

The key design choice is that displayed text and inserted raw token text can differ. The user sees a short pill label, but the input field retains the underlying token needed for later parsing and expansion.

## Top Bar and Status

The top bar is the compact summary of the current conversation state.

It shows:

- branding and window identity
- recent context pills
- model and token metadata (read from `conversation.llm_metadata`)

The menu bar shows a static "LLM" label. Per-tab running state is conveyed by indicators on the tab bar, not the menu bar.

## Tab Bar

The tab bar is a horizontal strip between the top bar and the main text area. It displays conversation tabs for switching between recent conversations.

`TabBarHandler` in `macllm/ui/tab_bar.py` renders the strip. It is called from `MacLLMUI.update_window()` on every layout pass.

### Tab Selection Logic

By default, the tab bar shows the last 5 conversations with the newest on the left. If the active conversation is older and falls outside this window, the bar centers on the active conversation with up to 2 tabs on each side.

### Visual Style

Tabs are Chrome-style rounded pills inside the strip:

- the active tab has a white fill with dark text (prominent)
- inactive tabs have a medium grey fill with subdued text (dimmer)
- titles are center-aligned and truncated to fit

### Keyboard Navigation

- **Option-Left** cycles to an older conversation
- **Option-Right** cycles to a newer conversation

These shortcuts only fire when the input field is empty. When text is present, the default word-jump behavior is preserved.

### Tab Indicators

Tabs show visual indicators for background activity:
- A running indicator on tabs where the conversation's agent is active
- An approval-needed indicator on tabs with a pending shell approval

### Click Handling

Each tab is a `_ClickableTab` (NSView subclass) that calls `MacLLMUI.switch_conversation(index)` on `mouseDown`. Switching is always allowed, even while agents are running in other tabs.

## History Browsing

History browsing is a separate interaction mode layered on top of the conversation view.

When active, the conversation text view becomes the keyboard target. The user can move through prior messages, copy them, or insert one back into the input field. This is handled by a dedicated delegate rather than by the normal input delegate.

## Layout Model

The window layout is computed dynamically from rendered content height.

The UI uses:

- a fixed-width quick-entry window
- a top bar
- a conversation tab bar
- a scrollable main text area
- a multi-line input area

Window height grows with content up to a screen-relative maximum, which keeps the interface compact for short exchanges but usable for long ones.
