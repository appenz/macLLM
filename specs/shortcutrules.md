# Shortcut Parsing Rules

macLLM supports two user-facing constructs with distinct semantics:

- **Commands** (`/`): Control behavior or expand to prompt text. Includes user-defined shortcuts and plugin-registered commands.
- **Context** (`@`): Add data/context to the conversation (files, clipboard, images, URLs, etc.).

Processing order: shortcuts expand first (text replacement), then both `/` commands and `@` tags are processed by plugins.

## Command Syntax (`/`)

Commands can be either:
1. **User-defined shortcuts**: Declared in TOML as two-element arrays: `["/trigger", "expansion text"]`.
2. **Plugin-registered commands**: Handled by plugins (e.g. `/fast`, `/slow`, `/think`).

User shortcuts are read from:
- The application-supplied TOML file `config/default_shortcuts.toml`
- Any `*.toml` file found in the user directory `~/.config/macllm/`

At runtime:
- User shortcuts: occurrences of the exact `/trigger` are replaced with the configured expansion before plugin processing.
- Plugin commands: processed by plugins which may modify request state (e.g., speed level) and remove the command from the prompt.

Example:
- In TOML: `["/blog", "Expand the following into paragraphs...\n---\n"]`
- In input: `Please /blog this:` → the `/blog` token is replaced with the configured text.
- In input: `Hello /fast` → the `/fast` command sets speed to fast and is removed from the prompt.

Configuration tags in TOML:

- Any entry whose trigger starts with `@` is treated as a configuration tag for plugins (not a user command).
- Example: `[@IndexFiles, "/some/path"]` is consumed by the file plugin to build an index for path tags.

## Context Syntax (`@`)

Tags are parsed in the user's input after shortcuts expand. The parsing rules are:

1. A tag runs until the first whitespace character: `@clipboard some text` → tag is `@clipboard`.
2. Backslash-escaped spaces are included: `@/path/with\ spaces/file.txt` → tag is `@/path/with spaces/file.txt`.
3. Quoted tags include everything until the closing quote or newline (quotes are stripped):
   - `@"~/My Home/foo"` → tag is `@~/My Home/foo`

Tags are handled by plugins that implement `get_prefixes()` and `expand(...)`, adding context to the conversation.

## Autocomplete and Highlighting (shared)

- The editor provides the same autocomplete popup and inline "pill" highlighting for both `/` commands and `@` tags.
- Typing `/` lists user-defined shortcuts and plugin-registered commands; typing `@` lists context tag prefixes and dynamic suggestions from plugins.
- Enter inserts the selected suggestion as a pill; Tab inserts the raw text and keeps it editable (quoted forms `@"..."` and `/"..."` are supported).
- Pills for commands show plain text (no icon). Context tag pills may show an icon as provided by the plugin's `display_string`.
- The UI applies a short minimum-length filter so suggestions appear after a few characters.

## Plugins and Tags

Tags live in the `macllm/tags/` directory and inherit from the base class `TagPlugin` (`macllm.tags.base.TagPlugin`).

- Each plugin should implement:
  - `get_prefixes() -> list[str]` — return all `@` (context) and/or `/` (command) prefixes the plugin should react to
  - `expand(tag: str, conversation, request) -> str` — return the replacement string to insert into the prompt
- Plugins may optionally implement dynamic autocomplete and display mapping.
- Some plugins can also expose configuration tags for use in TOML via `get_config_prefixes()` and `on_config_tag(...)`.

## Current Plugins (examples)

- ClipboardTag (`@clipboard`) — Inserts clipboard text or image as context.
- FileTag (path-like tags: `@/`, `@~`, `@"/`, `@"~`) — Reads file contents (up to 10 KB) as context; config tag `@IndexFiles` builds an index; `/reindex` triggers immediate re-indexing.
- URLTag (`@http://`, `@https://`) — Downloads and strips web page content as context.
- ImageTag (`@selection`, `@window`) — Captures screenshots for image analysis.
- SpeedTag (`/fast`, `/slow`, `/think`) — Adjusts processing speed (commands, not context).
- AgentTag (`@agent:<name>`) — Selects which agent runs the conversation (with autocomplete for registered agent names).

## Processing Order Summary

1. Expand all `/...` user shortcuts using the configured TOML mappings (text replacement).
2. Process all `/...` commands and `@...` tags using the loaded tag plugins, which may add context and replace tags/commands in-place. 