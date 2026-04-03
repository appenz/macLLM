# File Plugin Architecture

## Overview

`FileTag` is both a request-expansion plugin and the indexing backend for file-related agent tools.

This is the key design choice in the file subsystem: one component owns:

- path-style `@...` expansion
- indexed-file autocomplete
- semantic search over indexed files
- the shared index used by note tools
- mount-point management (logical names for indexed directories)

That keeps file discovery, file context injection, and tool path resolution consistent.

## Mount Points

Indexed directories are configured as named **mount points** in `config.toml`:

```toml
[index_dirs]
Private = "~/notes/private"
Work = "~/notes/work"
```

Each entry maps a logical mount name to an absolute directory path. The legacy list format (`index_dirs = [...]`) is also accepted; mount names are derived from directory basenames.

`MacLLM._apply_index_dirs_from_config()` reads `config.resolved_index_dirs()` (a `dict[str, str]`) and writes directly to `FileTag._mount_points` and `FileTag._indexed_directories`.

## Path Model

All note tools operate on **mount-relative paths** — e.g. `Private/todo.md` or `Work/projects/plan.md`. This keeps paths short, unambiguous across multiple roots, and avoids leaking absolute filesystem paths into agent context.

`FileTag` provides two classmethods for translation:

- `FileTag.resolve_mount_path(mount_path)` — converts `Private/todo.md` → `/Users/me/notes/private/todo.md`
- `FileTag.to_mount_path(abs_path)` — converts `/Users/me/notes/private/todo.md` → `Private/todo.md`

The note tool helper `validate_indexed_path()` tries mount-path resolution first, then falls back to absolute path validation for backward compatibility.

When an agent needs the real filesystem path (e.g. to pass to an external tool like `text2pdf`), it uses the `note_resolve_path` tool.

## Indexing Model

`FileTag.start_index_loop()` runs a background indexing loop that:

- rebuilds the basename/path index
- maintains txtai embeddings for semantic search
- caches embedding state to disk
- supports explicit rebuild through `/reindex`

The index is global to the running app and shared by autocomplete, context expansion, and note tools.

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

## Relationship to Note Tools

The note tools in `macllm/tools/note.py` depend on the mount-point and indexed-directory model.

Two boundaries matter:

- `FileTag` owns discovery, autocomplete, context expansion, semantic search, and mount-point path translation
- note tools own read/write/move/delete operations, folder management, folder search, and path resolution — validating that all paths stay inside mounted directories

This means the file plugin is not just a UI convenience layer. It is also the discovery, search, and path-resolution backend for the note-tool subsystem.
