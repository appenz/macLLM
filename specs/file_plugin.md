# File Plugin Architecture

## Overview

`FileTag` provides file autocomplete, path-tag rewriting, and the shared semantic index used by
`search_notes`. File contents are read only by filesystem tools.

## Indexing

Every filesystem mount with `index = true` is recursively indexed for `.md` and `.txt` files.
Host paths remain internal document identifiers; all paths exposed to users and agents are the
mount's absolute virtual paths.

The index supports:

- basename autocomplete for `@...`
- semantic note search
- periodic refresh and explicit `/reindex`
- an on-disk txtai embedding cache

Filesystem mutations on indexed mounts request a refresh.

## Path Tags

Indexed autocomplete inserts the virtual path. Explicit host paths grant their parent directory
and are rewritten beneath `/host`, so every generated `read_file` call uses the virtual
filesystem.

The plugin never reads file content or bypasses filesystem permissions. `read_file` handles text
chunking, images, and Sources.
