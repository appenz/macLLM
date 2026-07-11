# Agent Filesystem

## Overview

Agents see one filesystem rooted at `/`. File tools use these virtual paths regardless of where
the underlying data lives.

The filesystem makes notes, memory, skills, artifacts, temporary state, and approved host files
available through one consistent interface.

## Namespace

```text
/
├── notes/       ← mounted from user-selected folders. Shared and writable.
├── memory/      ← mounted from a user-selected folder. Shared and writable; replaces old memory.
├── skills/      ← mounted from configured skill folders. Shared and read-only.
├── home/        ← private durable workspace for generated artifacts.
└── host/        ← host filesystem; requires user permission.
```

The available-skill catalog is still supplied to agents out of band; skill contents are loaded
with `read_file`.

The parent agent and its subagents share the conversation's `/home`. Other conversations cannot
access it.

## Mount Model

Each conversation has a real root directory containing its private workspace. Shared and host
mounts are virtual: their paths are resolved to configured or approved host paths without copying
their contents into the conversation root.

Inactive conversation roots are garbage-collected after seven days. Shared mounted data is never
garbage-collected with a conversation root.

## Tools

- `read_file(path)` reads a file.
- `write_file(path, content)` creates or replaces a file.
- `append_file(path, content)` appends to a file.
- `list_directory(path)` lists a directory.
- `copy_file(source, destination)` copies a file or directory.
- `delete_file(path, recursive=False)` deletes a file or directory.
- `create_directory(path)` creates one directory; its parent directory must already exist.
- `search_notes(query)` semantically searches embeddings scoped to `/notes`.
- `grep_notes(pattern)` searches `/notes` by text pattern.

All filesystem tools resolve paths through the same namespace and enforce the mount's access
policy.

Search and grep discover files; file contents and mutations use the filesystem tools.
