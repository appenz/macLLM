# Tag Plugin Architecture

## Overview

Tag plugins implement UI/input sugar for `@...` and plugin-owned `/...` tokens.

They let users write shorter requests by turning shorthand into plain prompt text or run options
such as selected agent, selected speed tier, and tool disabling. They also power autocomplete and
pill display. They are not a data access path.

## Architectural Principle

Tag plugins operate at the UI/request-syntax level:

- rewrite prompt text
- set run options
- provide autocomplete and pill display strings
- They do not read or marshal dynamic external resources such as clipboard contents, user files, URLs, screenshots, or images.
- Data access shorthand must rewrite to normal tool-use instructions, for example `@clipboard` -> `Clipboard (use read_clipboard())`.

Skills are adjacent but separate. User-invocable `/skill` rewriting happens before plugin processing and is
owned by `SkillsRegistry`, not by `TagPlugin`. Skills may read predefined configured skill files because those files are prompt assets, not dynamic user resources. After that rewrite step, plugins process the remaining
`@...` and plugin-owned `/...` tokens.

## Request Rewrite Model

The base class is `TagPlugin` in `macllm/tags/base.py`. Plugins are discovered from
`macllm/tags/*_tag.py` and instantiated per `MacLLM` instance.

Input sugar is applied by `UserRequest.process_tags()` in `macllm/core/user_request.py`.

1. `Conversation.submit()` builds a `UserRequest`.
2. Any user-invocable `/skill` invocation is rewritten by `SkillsRegistry`.
3. `UserRequest.find_shortcuts()` scans the prompt for `@...` and `/...` tokens.
4. Tokens are matched against the plugin prefix index, longest prefix first.
5. The matching plugin's `expand(...)` method is called.
6. The returned string replaces the original token inside the rewritten prompt.

Key constraints:

- rewriting happens on the per-request prompt, not on stored `Conversation` messages
- plugins may set run options on `UserRequest`, for example speed, selected agent, or no-tools mode
- plugins must not read clipboard data, files, URLs, screenshots, or other external data
- plugins must not attach image payloads or append hidden text payloads
- user-facing data access shorthand should rewrite to an instruction that names the relevant tool

## URL Tags

`@http://...` and `@https://...` tags are syntax sugar for web-fetch work.

They should rewrite to prompt text that preserves the URL and tells the model to use the web fetch tool if the page needs to be read. Reading the page is always a tool call, and a source is added only when the page is directly fetched.

## Data Access Tags

Data access tags are input affordances only:

- `@clipboard` rewrites to `Clipboard (use read_clipboard())`
- file path pills rewrite to text that preserves the path and points at `read_file(path)`
- `@selection` rewrites to text that points at `capture_selection()`
- `@window` rewrites to text that points at `capture_window()`

These tags never read their targets. The agent must call the tool to receive an observation.

## Autocomplete and Configuration

Autocomplete is plugin-driven through optional hooks on `TagPlugin`.
`AutocompleteController` combines static prefix matches with plugin-provided dynamic suggestions.
Static matches are shown first so built-in tags keep precedence over broader providers such as file search.

Plugins may also expose configuration hooks through `get_config_prefixes()` and `on_config_tag(...)`.
This keeps plugin-specific setup, such as file indexing configuration, in the same subsystem as runtime rewriting.