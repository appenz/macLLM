# Request Parsing Rules

## Overview

macLLM has two request-expansion mechanisms:

- leading `/skill` expansion, owned by `SkillsRegistry`
- `@...` and plugin-owned `/...` token expansion, owned by tag plugins

## Processing Order

The current processing order is:

1. Start with the original prompt.
2. If the prompt begins with a skill command, `SkillsRegistry.expand_manual_invocation()` expands it.
3. Build a `UserRequest` from that result.
4. `UserRequest.process_tags()` scans the expanded prompt for `@...` and `/...` tokens.
5. Matching plugins rewrite the expanded prompt and may update request state such as agent, speed, images, or context.
6. The original prompt is stored in conversation history, while the expanded prompt is sent to the agent.

## Token Syntax

`UserRequest.find_shortcuts()` applies the same tokenization rules to both `@` and `/` forms.

- unquoted tokens run until the first unescaped whitespace character
- backslash-escaped spaces are included in the token
- quoted forms such as `@"..."` or `/"..."` run until the closing quote or newline, and the quotes are removed

This allows paths and other arguments with spaces to be represented as a single token.

## Matching Model

The matching model has two layers.

For expansion, matching is strict and prefix-based.

- plugins declare the prefixes they own
- `MacLLM` builds a prefix index once at startup
- expansion uses the longest matching prefix
- replacement happens back-to-front in the prompt so earlier replacements do not shift later token offsets

This keeps expansion deterministic even when prefixes overlap.

For autocomplete, matching is broader.

- plugins can offer suggestions for their declared prefixes
- plugins can also opt into catch-all autocomplete without owning those tokens for expansion

The file plugin is the main example. It does not own the generic `@` prefix for expansion, because that
would shadow plugins such as `@clipboard`. But it does participate in generic `@...` autocomplete so it
can suggest indexed files by basename. Those suggestions insert a raw path token that later matches the
file plugin's real expansion prefixes.

## Autocomplete

Autocomplete follows the same split as parsing.

- `/` suggestions include skill commands and plugin-owned slash commands
- `@` suggestions include plugin prefixes and plugin-provided dynamic suggestions
- plugins may provide a display string different from the raw inserted token

The inserted token remains the raw text that later parsing and expansion will consume.