# Request Parsing Rules

## Overview

macLLM has two request-rewrite mechanisms:

- user-invocable `/skill` rewriting, owned by `SkillsRegistry`
- `@...` and plugin-owned `/...` token rewriting, owned by tag plugins

## Processing Order

The current processing order is:

1. Start with the original prompt.
2. `SkillsRegistry.expand_manual_invocation()` rewrites user-invocable skill commands wherever they appear in the prompt.
3. Build a `UserRequest` from that result.
4. `UserRequest.process_tags()` scans the rewritten prompt for `@...` and remaining `/...` tokens.
5. Matching plugins rewrite the prompt and may update run options such as agent, speed, or no-tools mode.
6. Data-access shorthand rewrites to plain tool-use instructions, for example `@clipboard` -> `Clipboard (use read_clipboard())`.
7. The original prompt is stored in conversation history, while the rewritten prompt is sent to the agent.

## Token Syntax

`UserRequest.find_shortcuts()` applies the same tokenization rules to both `@` and `/` forms.

- unquoted tokens run until the first unescaped whitespace character
- backslash-escaped spaces are included in the token
- quoted forms such as `@"..."` or `/"..."` run until the closing quote or newline, and the quotes are removed

This allows paths and other arguments with spaces to be represented as a single token.

## Matching Model

The matching model has two layers.

For rewriting, matching is strict and prefix-based.

- plugins declare the prefixes they own
- `MacLLM` builds a prefix index once at startup
- rewriting uses the longest matching prefix
- replacement happens back-to-front in the prompt so earlier replacements do not shift later token offsets

This keeps rewriting deterministic even when prefixes overlap.

For autocomplete, matching is broader.

- plugins can offer suggestions for their declared prefixes
- plugins can also opt into catch-all autocomplete without owning those tokens for rewriting

The file plugin is the main example. It does not own the generic `@` prefix for rewriting, because that
would shadow plugins such as `@clipboard`. But it does participate in generic `@...` autocomplete so it
can suggest indexed files by basename. Those suggestions insert a raw path token that later matches the
file plugin's real rewrite prefixes.

## Autocomplete

Autocomplete follows the same split as parsing.

- `/` suggestions include skill commands and plugin-owned slash commands
- `@` suggestions include plugin prefixes and plugin-provided dynamic suggestions
- plugins may provide a display string different from the raw inserted token

The inserted token remains the raw text that later parsing and rewriting will consume.