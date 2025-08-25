from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .base import TagPlugin


class FileTag(TagPlugin):
    """Handle directory indexing via *config tag* `@IndexFiles` and expose
    `@file` tag that lets the user embed the contents of an indexed file.
    """

    # Public constants
    PREFIX_CONFIG = "@IndexFiles"

    # Prefixes that represent plain path tags (previously handled by PathTag)
    PATH_PREFIXES = ["@/", "@~", "@\"/", "@\"~"]

    # Also allow generic "@" prefix for autocomplete (without explicit keyword)
    # Autocomplete suggestions will only be generated once the user has typed
    # at least *MIN_CHARS* characters after the leading "@".
    MIN_CHARS = 3
    EXTENSIONS = (".txt", ".md")
    MAX_CONTEXT_LEN = 10 * 1024  # 10 KB cap identical to old PathTag

    # ------------------------------------------------------------------
    # Object lifecycle & in-memory index
    # ------------------------------------------------------------------
    def __init__(self, macllm):
        super().__init__(macllm)
        # List of tuples (basename_lower, full_path)
        self._index: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # TagPlugin interface – configuration tags
    # ------------------------------------------------------------------
    def get_config_prefixes(self) -> List[str]:
        return [self.PREFIX_CONFIG]

    def on_config_tag(self, tag: str, value: str):  # noqa: D401
        """Called during shortcut loading for each `@IndexFiles` entry.

        *value* is expected to be a path string.  We walk the directory
        recursively and add eligible files to *self._index*."""
        # Accept optional quotes and env vars
        dir_path = value.strip().strip('"')
        dir_path = os.path.expandvars(os.path.expanduser(dir_path))

        if os.path.isdir(dir_path) is False:
            if self.macllm.debug:
                self.macllm.debug_log(f"@IndexFiles: Not a directory – {dir_path}", 2)
            return

        for fp in Path(dir_path).rglob("*"):
            if fp.is_file() and fp.suffix.lower() in self.EXTENSIONS:
                basename = fp.name
                self._index.append((basename.lower(), str(fp)))

        # Sort alphabetically by basename for deterministic ordering
        self._index.sort(key=lambda t: t[0])

        if self.macllm.debug:
            self.macllm.debug_log(
                f"Indexed {len(self._index)} files from {dir_path}", 0
            )

    # ------------------------------------------------------------------
    # TagPlugin interface – normal expansion
    # ------------------------------------------------------------------
    def get_prefixes(self) -> List[str]:
        # We now own *all* path-like tags.  Return only prefixes that should
        # trigger *expansion*.  The generic "@" is **excluded** here so that
        # other plugins (e.g. ClipboardTag) are not shadowed during
        # expansion.  We still use the generic symbol for autocomplete via
        # *match_any_autocomplete()*.
        return self.PATH_PREFIXES

    # ------------------------------------------------------------------
    # Catch-all autocomplete flag
    # ------------------------------------------------------------------
    def match_any_autocomplete(self) -> bool:  # noqa: D401
        """Indicate that this plugin wants to be queried for autocomplete
        suggestions for *all* "@…" fragments, regardless of prefix match."""
        return True

    def expand(self, tag: str, conversation, request):
        """Read the referenced file (tag may be a plain path or an internal
        @file tag), add it to *conversation* context, and return a
        ``RESOURCE:<handle>`` replacement string."""

        # Only handle tags that use one of our path prefixes.
        if any(tag.startswith(p) for p in self.PATH_PREFIXES):
            # Strip the leading '@' to get the raw path (quotes may follow)
            path_spec = tag[1:]
        else:
            # Unknown prefix – let other plugins handle it
            return tag

        if path_spec.startswith('"') and path_spec.endswith('"'):
            path_spec = path_spec[1:-1]

        path_spec = os.path.expanduser(path_spec)

        try:
            content = self._read_file(path_spec)
        except Exception as exc:  # pylint: disable=broad-except
            if self.macllm.debug:
                self.macllm.debug_exception(exc)
            return tag  # leave unmodified so the user sees the failure

        context_name = conversation.add_context(
            Path(path_spec).name,
            path_spec,
            "path",
            content,
            icon="📁"
        )
        return f"RESOURCE:{context_name}"

    # ------------------------------------------------------------------
    # Dynamic autocomplete hooks
    # ------------------------------------------------------------------
    def supports_autocomplete(self) -> bool:
        return True

    def autocomplete(self, fragment: str, max_results: int = 10) -> List[str]:
        """Return suggestions for *fragment* using either live filesystem
        exploration or the pre-built index."""

        # Path-style fragments are handled via live filesystem completion without
        # applying the *MIN_CHARS* limit so that patterns like "@/" start
        # suggesting immediately.
        if any(fragment.startswith(p) for p in self.PATH_PREFIXES):
            return self._autocomplete_live_path(fragment, max_results)

        # For indexed substring search we enforce the minimum length to avoid
        # overly eager suggestions.
        search_term = fragment[1:]
        if len(search_term) < self.MIN_CHARS:
            return []

        term_lc = search_term.lower()
        matches = [fp for base, fp in self._index if term_lc in base]
        matches.sort()
        raw_tags: list[str] = []
        for p in matches[:max_results]:
            raw_tags.append(f'@"{p}"')
        return raw_tags

    def display_string(self, suggestion: str) -> str:
        if suggestion.startswith('@'):
            path_spec = suggestion[1:]
        else:
            return suggestion
        if path_spec.startswith('"') and path_spec.endswith('"'):
            path_spec = path_spec[1:-1]
        # Keep trailing slash indicator for directories
        if path_spec.endswith('/'):
            name = Path(path_spec[:-1]).name + '/'
        else:
            name = Path(path_spec).name
        return "📁" + name

    # ------------------------------------------------------------------
    # Live path completion helpers
    # ------------------------------------------------------------------
    def _parse_path_fragment(self, fragment: str) -> tuple[str, str]:
        """Return (dir_raw, prefix) for *fragment* like '@~/dev/proj'.
        *dir_raw* retains the original tilde or absolute prefix and always ends
        with '/'. *prefix* is the partial filename after the last '/'."""
        # Strip leading '@'
        path_part = fragment[1:]
        if path_part.startswith('"'):
            path_part = path_part[1:]
        # Ensure we're dealing with something that looks like a path
        if not (path_part.startswith('/') or path_part.startswith('~')):
            raise ValueError('Not a path fragment')
        last_sep = path_part.rfind('/')
        if last_sep == -1:
            raise ValueError('No directory component')
        dir_raw = path_part[: last_sep + 1]
        prefix = path_part[last_sep + 1 :]
        return dir_raw, prefix

    def _autocomplete_live_path(self, fragment: str, max_results: int) -> List[str]:
        try:
            dir_raw, prefix = self._parse_path_fragment(fragment)
        except ValueError:
            return []
        dir_abs = os.path.expanduser(dir_raw)
        if not os.path.isdir(dir_abs):
            return []
        suggestions: list[str] = []
        try:
            with os.scandir(dir_abs) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
                for entry in entries:
                    if prefix and not entry.name.lower().startswith(prefix.lower()):
                        continue
                    p_raw = f"{dir_raw}{entry.name}"
                    if entry.is_dir():
                        p_raw += '/'
                    suggestions.append(f'@"{p_raw}"')
                    if len(suggestions) >= max_results:
                        break
        except PermissionError:
            return []
        return suggestions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_file(self, filepath: str) -> str:
        """Read a text file with size & binary checks (10 KB limit)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(self.MAX_CONTEXT_LEN)
            if "\0" in content:
                raise ValueError("File appears to be binary")
        return content 