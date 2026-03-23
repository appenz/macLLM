# Tag Plugin Architecture

## Overview

Tag plugins are the request-expansion layer for `@...` and `/...` tokens.

They turn user-facing shorthand into request state such as embedded context, selected agent,
selected speed tier, attached images, and autocomplete suggestions. This layer sits between
the original prompt and agent execution.

Skills are adjacent but separate. Leading `/skill` expansion happens before plugin processing and is
owned by `SkillsRegistry`, not by `TagPlugin`. After that expansion step, plugins process the remaining
`@...` and plugin-owned `/...` tokens.

## Request Expansion Model

The base class is `TagPlugin` in `macllm/tags/base.py`. Plugins are discovered from
`macllm/tags/*_tag.py` and instantiated per `MacLLM` instance.

Request expansion is driven by `UserRequest.process_tags()` in `macllm/core/user_request.py`.

1. `MacLLM.handle_instructions()` builds a `UserRequest`.
2. Any leading `/skill` invocation is expanded by `SkillsRegistry`.
3. `UserRequest.find_shortcuts()` scans the prompt for `@...` and `/...` tokens.
4. Tokens are matched against the plugin prefix index, longest prefix first.
5. The matching plugin's `expand(...)` method is called.
6. The returned string replaces the original token inside `expanded_prompt`.

Key design decisions:

- expansion happens on `UserRequest.expanded_prompt`, not on stored `Conversation.messages`
- plugins may mutate `UserRequest` and `Conversation` as side effects
- context plugins maintain both `Conversation.context_history` for the UI and embedded context in `expanded_prompt` for the agent

## Autocomplete and Configuration

Autocomplete is plugin-driven through optional hooks on `TagPlugin`.
`AutocompleteController` combines static prefix matches with plugin-provided dynamic suggestions.
Static matches are shown first so built-in tags keep precedence over broader providers such as file search.

Plugins may also expose configuration hooks through `get_config_prefixes()` and `on_config_tag(...)`.
This keeps plugin-specific setup, such as file indexing configuration, in the same subsystem as runtime expansion.