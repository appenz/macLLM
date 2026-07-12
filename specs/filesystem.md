# Agent Filesystem

## Overview

Agents see one filesystem rooted at `/`. File tools use these virtual paths regardless of where
the underlying data lives.

The filesystem makes notes, memory, skills, artifacts, temporary state, and approved host files
available through one consistent interface.

## Namespace

```text
/
├── notes/       ← configured shared mounts, typically indexed.
├── memory/      ← configured shared mount; replaces old memory.
├── skills/      ← configured shared mounts for skill files.
├── home/        ← private durable workspace for generated artifacts.
└── host/        ← host filesystem; requires user permission.
```

The available-skill catalog is still supplied to agents out of band; skill contents are loaded
with `read_file`.

The parent agent and its subagents share the conversation's `/home`. Other conversations cannot
access it.

## Mount Model

Shared directories use one configuration primitive:

```toml
[filesystem.mounts.notes_a16z]
virtual = "/notes/a16z"
path = "~/Notes/a16z"
supervisor_access = "read-write"
subagent_access = "read-only"
index = true
```

Access is `read-write`, `read-only`, or `none`. Mounts with `index = true` feed note search.
Resolution uses the longest matching virtual path and enforces the selected agent access before
mapping it to `path`.

`/memory` has no default backing directory. Users who want persistent agent memory configure an
explicit mount with `supervisor_access = "read-write"`, `subagent_access = "read-only"`, and
`index = false`.

Core adds runtime mounts to the same table: conversation-scoped `/home` and user-granted `/host`
paths. Directory listings are derived from the table.

Conversation roots live under
`~/Library/Application Support/macLLM/filesystems/<conversation-id>/`, with `/home` stored in its
`home/` subdirectory.

Fresh conversations create this structure once. Missing or altered structure is a filesystem
error; path resolution never repairs it. At startup, roots more than seven days old are deleted.
Shared mounted data is never garbage-collected with a conversation root.

## Tools

- `read_file(path)` reads a file.
- `write_file(path, content)` creates or replaces a file.
- `append_file(path, content)` appends to a file.
- `list_directory(path)` lists a directory.
- `copy_file(source, destination)` copies a file or directory.
- `delete_file(path, recursive=False)` deletes a file or directory.
- `create_directory(path)` creates one directory; its parent directory must already exist.
- `search_notes(query)` semantically searches embeddings scoped to `/notes`.

All filesystem tools resolve paths through the same namespace and enforce the mount's access
policy.

Search discovers files; file contents and mutations use the filesystem tools.
