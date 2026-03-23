# File Plugin Architecture

## Overview

`FileTag` is both a request-expansion plugin and the indexing backend for file-related agent tools.

This is the key design choice in the file subsystem: one component owns:

- path-style `@...` expansion
- indexed-file autocomplete
- semantic search over indexed files
- the shared index used by file tools

That keeps file discovery, file context injection, and file-tool lookup consistent.

## Indexing Model

Indexed directories come from `index_dirs` in runtime config, not from shortcut files.
`MacLLM._apply_index_dirs_from_config()` passes those directories into `FileTag` through the plugin configuration hook.

`FileTag.start_index_loop()` runs a background indexing loop that:

- rebuilds the basename/path index
- maintains txtai embeddings for semantic search
- caches embedding state to disk
- supports explicit rebuild through `/reindex`

The index is global to the running app and shared by autocomplete, context expansion, and file tools.

## Request Model

The file plugin handles two different request patterns.

- path tags such as `@/...` and `@~/...` expand directly to file content embedded in the request
- generic `@...` autocomplete can resolve to indexed files by basename match

When a file is expanded into a request, `FileTag` reads the file, registers it in `Conversation.context_history`,
and returns an embedded context block inside `UserRequest.expanded_prompt`.

## Autocomplete Model

The file plugin participates in autocomplete in two ways:

- live filesystem completion for explicit path prefixes
- indexed basename search for generic `@...` fragments

It also uses `match_any_autocomplete()` so it can offer indexed-file matches even when the fragment
does not start with one of its explicit path prefixes.

Display and insertion are intentionally different:

- the UI shows a short basename-oriented display string
- the raw inserted token preserves the full path so expansion later has exact file identity

## Relationship to File Tools

The file tools in `macllm/tools/file.py` depend on the same indexed-directory model.

Two boundaries matter:

- `FileTag` owns discovery, autocomplete, context expansion, and semantic search
- file tools own read/write/move/delete operations and validate that paths stay inside indexed directories

This means the file plugin is not just a UI convenience layer. It is also the discovery and search backend for the file-tool subsystem.
