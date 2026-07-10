# File Plugin Architecture

## Overview

`FileTag` is the file input-sugar and indexing backend for file-related agent tools.

This is the key design choice in the file subsystem: one component owns:

- path-style `@...` autocomplete and prompt rewriting
- indexed-file autocomplete
- semantic search over indexed files
- the shared index used by note tools
- mount-point management (logical names for indexed directories)

That keeps file discovery, autocomplete, and tool path resolution consistent. Reading file contents belongs to tools.

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

All note tools operate on **mount-relative paths** — e.g. `Private/todo.md` or `Work/projects/plan.md`. This keeps paths short and unambiguous across multiple roots.

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

The index is global to the running app and shared by autocomplete and note tools.

Semantic indexing loads the embedding model from the app-managed local copy
installed and verified by `make install`.

## Request Model

The file plugin handles input ergonomics only.

- path tags such as `@/...` and `@~/...` rewrite to plain prompt text that preserves the path and tells the model to call `read_file(path)` if it needs to read the file
- generic `@...` autocomplete can resolve to indexed files by basename match and insert a raw path token
- directory shortcuts such as `@home` may grant directory access for tools such as shell or `read_file`, but do not read files

The file plugin must not read file contents or load image files. Text files and image files are read by `read_file(path)`, which returns an observation during the agent loop.

## Autocomplete Model

The file plugin participates in autocomplete in two ways:

- live filesystem completion for explicit path prefixes
- indexed basename search for generic `@...` fragments

It also uses `match_any_autocomplete()` so it can offer indexed-file matches even when the fragment
does not start with one of its explicit path prefixes.

Display and insertion are intentionally different:

- the UI shows a short basename-oriented display string
- the raw inserted token preserves the full path so the rewritten prompt can contain the exact `read_file(path)` argument

## Relationship to Note Tools

The note tools in `macllm/tools/note.py` depend on the mount-point and indexed-directory model.

Two boundaries matter:

- `FileTag` owns discovery, autocomplete, input rewriting, semantic search, and mount-point path translation
- note tools own read/write/move/delete operations, folder management, folder search, and path resolution — validating that all paths stay inside mounted directories

This means the file plugin is not just a UI convenience layer. It is also the discovery, search, and path-resolution backend for the note-tool subsystem. Direct file payload access still happens through tools.

## Direct File Reads

General user-file reads are handled by `read_file(path, start=0, max_chars=...)` in the tools layer.

- Text files return bounded text observations, with truncation markers when more content is available.
- Image files return image-bearing observations.
- Successful direct file reads add a file Source to the conversation.
- Search results, folder listings, autocomplete suggestions, and directory traversal do not add Sources.
- The tool enforces the file access policy. The tag plugin does not bypass that policy.
