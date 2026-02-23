# File Plugin – Design Specification

## Overview

The **file-plugin** adds four user-facing capabilities:

1. **Directory indexing with auto-completion** – The shortcut tag `@IndexFiles "<dir>"` declared in any shortcuts TOML file triggers a *recursive* scan of the specified directory. Every file whose basename ends with `.txt` or `.md` is recorded. The files found will be auto-completed.
2. **Path auto-completion** - If the user types a tag with a partial path (e.g. `@~/dev/projects/`) it will suggest completions of the path. Works like a command line autocomplete.
3. **File reference tags** – Users can reference an indexed file in chat by typing `@<substring>` (case-insensitive). Once 3 characters are typed, the auto-complete popup lists up to **10** matching files by basename. Selecting a suggestion inserts a pill that shows only the basename, but when the message is processed the full path is expanded and its contents are attached to the conversation.
4. **Embedding-based search** – The indexed files are embedded using a sentence-transformer model (`all-mpnet-base-v2` via txtai). Agent tools can call `FileTag.search(query)` to find semantically relevant files and `FileTag.get_file_content(file_id)` to retrieve their full content.

## Constants

```python
class FileTag(TagPlugin):
    PREFIX_CONFIG   = "@IndexFiles"
    PREFIX_REINDEX  = "/reindex"
    EXTENSIONS      = (".txt", ".md")
    MIN_CHARS       = 3                    # Min chars for indexed autocomplete
    MAX_CONTEXT_LEN = 10 * 1024            # 10 KB cap for path-tag file reads
    MAX_FULL_FILE_LEN = 10 * 1000          # Cap for get_file_content()
    SEARCH_PREVIEW_LEN = 1000              # Preview length in search results
    SEARCH_RESULTS_COUNT = 5               # Default number of search results
    REINDEX_INTERVAL = 5 * 60              # Seconds between periodic re-indexes
```

## Behaviour Summary

- Indexing runs in a background daemon thread. The first cycle runs immediately at startup, then repeats every `REINDEX_INTERVAL` seconds. The `/reindex` command triggers an immediate rebuild.
- The embedding index supports incremental updates: only new, changed, or deleted files are re-embedded on subsequent cycles. Embeddings are cached to disk.
- Search is **case-insensitive** and matches any substring of the basename.
- Up to **10** suggestions are shown, ordered alphabetically.
- When selected, the pill shows the basename only; expansion adds the file's contents (subject to the `MAX_CONTEXT_LEN` limit).
- Multiple `@IndexFiles` tags may appear; all indexed files share the same global pool.

## High-level Flow

1. **Startup order**
   a. `TagPlugin.load_plugins()` runs first.
   b. `ShortCut.init_shortcuts()` then reads every shortcuts TOML file.
   c. Each `trigger` in the TOML is checked: if it matches a *config tag* that some plugin registered (see below), the loader calls `plugin.on_config_tag(trigger, value)` instead of storing it as a normal shortcut.
2. The file-plugin's `on_config_tag()` receives every `@IndexFiles` entry and collects directories for indexing.
3. `FileTag.start_index_loop()` starts a daemon thread that calls `build_index()` and `_build_embeddings()` periodically.
4. While the UI is running, the input field's autocomplete system asks every plugin that *supports dynamic completion* for suggestions.
5. When the user hits Enter to send the message, the normal tag-expansion pipeline (`UserRequest.process_tags`) calls the file-plugin's `expand()` method which
   - looks up the chosen full path,
   - adds the contents to the conversation context, and
   - returns a `context:<context_name>` block.

## Implementation

### FileTag Responsibilities

1. **`get_config_prefixes()` → `["@IndexFiles"]`**
2. **`on_config_tag()`**
   - Resolve `~` and environment variables, accept quoted paths.
   - Collect directory for later indexing (deduplicates).
3. **`get_prefixes()` → `["@/", "@~", "@\"/", "@\"~", "/reindex"]`**
4. **`match_any_autocomplete()` → `True`**
   - Receives autocomplete callbacks for all `@…` fragments, enabling generic substring search.
5. **`supports_autocomplete()` → `True`**
6. **`autocomplete(fragment)`**
   - For path-style fragments (`@/`, `@~`): live filesystem completion via `_autocomplete_live_path()`.
   - For other `@` fragments: filter indexed basenames where `search_term in basename.lower()`.
   - Return up to 10 items sorted alphabetically.
   - Each item is returned in *raw* form: `@"<full_path>"`.
7. **`display_string(suggestion)`**
   - Return `"📁" + basename` (with trailing `/` for directories).
8. **`expand(tag, conversation, request)`**
   - If `/reindex`: trigger a re-index and return `""`.
   - For path tags: strip the leading `@` and surrounding quotes, read file, enforce `MAX_CONTEXT_LEN` & binary check.
   - Add context and return a `context:<handle>` block.

### Class Methods (for Agent Tools)

- **`search(query, n=5, timeout=60.0)`** – Semantic search over indexed files using txtai embeddings. Returns `list[tuple[int, float, str, str, bool]]` of `(file_id, score, filepath, preview, truncated)`.
- **`get_file_content(file_id)`** – Retrieve full content (up to `MAX_FULL_FILE_LEN`) of an indexed file by its ID. Returns `(content, filepath)`.

### Autocomplete Integration (UI)

`AutocompleteController` is extended so that when a fragment starts with any dynamic-autocomplete prefix it asks the owning plugin for suggestions and displays each with `plugin.display_string(s)`. Plugins returning `True` from `match_any_autocomplete()` are consulted for all `@` fragments regardless of prefix. The *committed text* inserted into the NSTextView remains the **raw suggestion**, ensuring `expand()` receives the full path later.
