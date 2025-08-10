# File Plugin – Design Specification

## Overview

The **file-plugin** adds three user-facing capabilities:

1. **Directory indexing with auto-completion** – The shortcut tag `@IndexFiles "<dir>"` declared in any shortcuts TOML file triggers a *recursive* scan of the specified directory. Every file whose basename ends with `.txt` or `.md` is recorded (no size limit at index-time). The files found will be auto-completed.
2. **Path auto-completion** - If the user types a tag with a partial path (e.g. `@~/dev/projects/`) it will suggestions for completions of the path. Works like a command line autocomplete.
3. **File reference tags** – Users can reference an indexed file in chat by typing `@<substring>` (case-insensitive). Once 3 characters are typed, the auto-complete popup lists up to **10** matching files by basename. Selecting a suggestion inserts a pill that shows only the basename, but when the message is processed the full path is expanded and its contents are attached to the conversation.

## Behaviour Summary

- Indexing happens **once at application startup**.
- Search is **case-insensitive** and matches any substring of the basename.
- Up to **10** suggestions are shown, ordered alphabetically.
- When selected, the pill shows the basename only; expansion adds the file's contents (subject to the same 10 KB limit used by `@path`).
- Multiple `@IndexFiles` tags may appear; all indexed files share the same global pool used by `@file`.

## High-level Flow

1. **Startup order**
   a. `TagPlugin.load_plugins()` runs first.
   b. `ShortCut.init_shortcuts()` then reads every shortcuts TOML file.
   c. Each `trigger` in the TOML is checked: if it matches a *config tag* that some plugin registered (see below), the loader calls `plugin.on_config_tag(trigger, value)` instead of storing it as a normal shortcut.
2. The file-plugin's `on_config_tag()` receives every `@IndexFiles` entry and builds an in-memory index: `List[FileEntry]` where `FileEntry = (basename, full_path)`.
3. While the UI is running, the input field's autocomplete system asks every plugin that *supports dynamic completion* for suggestions.
4. When the user hits ↩ to send the message, the normal tag-expansion pipeline (`UserRequest.process_tags`) calls the file-plugin's `expand()` method which
   - looks up the chosen full path,
   - adds the contents to the conversation context, and
   - returns `RESOURCE:<context_name>`.

## Implementation

### File-Plugin Responsibilities

```python
class FileTag(TagPlugin):
    PREFIX_CONFIG   = "@IndexFiles"
    EXTENSIONS      = (".txt", ".md")
    MAX_CONTEXT_LEN = 10,000
```

1. **`get_config_prefixes()` ➜ `["@IndexFiles"]`**
2. **`on_config_tag()`**
   - Resolve `~` and environment variables, accept quoted paths.
   - Walk directory recursively (`glob("**/*")`).
   - Store any file ending in the allowed extensions. Use a simple in-memory list or `dict[basename, full_path]` (if duplicates exist keep first hit or keep all – order alphabetical).
3. **`supports_autocomplete()` ➜ `True`**
4. **`autocomplete(fragment)`**
   - Filter indexed basenames where `search_term in basename.lower()`.
   - Return up to 10 items sorted alphabetically.
   - Each item is returned in *raw* form: `@"<full_path>"` (quoted if path contains spaces).
5. **`display_string(suggestion)`**
   - Return `os.path.basename(suggestion.strip('@').strip('"'))` – i.e. just the filename.
6. **`expand(tag, conversation)`**
   - Strip the leading `@` and surrounding quotes, read file.
   - Enforce `MAX_CONTEXT_LEN` & binary check identical to `PathTag`.
   - Add context and return `RESOURCE:<handle>`.

### Autocomplete Integration (UI)

`AutocompleteController` is extended so that when a fragment starts with any dynamic-autocomplete prefix it asks the owning plugin for suggestions and displays each with `plugin.display_string(s)`. The *committed text* inserted into the NSTextView remains the **raw suggestion**, ensuring `expand()` receives the full path later. 