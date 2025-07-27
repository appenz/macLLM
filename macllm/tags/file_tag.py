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
    PREFIX_REF = "@file"  # **internal** prefix used only for UI/logic

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
        # We now own *all* path-like tags.  Return:
        #   • Internal @file prefix (historical, not shown to the user)
        #   • All explicit path prefixes ("@/", "@~", etc.)
        #   • Generic "@" for autocomplete hook
        return [self.PREFIX_REF, "@"] + self.PATH_PREFIXES

    def expand(self, tag: str, conversation):
        """Read the referenced file (tag may be a plain path or an internal
        @file tag), add it to *conversation* context, and return a
        ``content:<handle>`` replacement string."""

        # Determine *path_spec* depending on which prefix we received.
        if tag.startswith(self.PREFIX_REF):
            path_spec = tag[len(self.PREFIX_REF) :]
        elif any(tag.startswith(p) for p in self.PATH_PREFIXES):
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
        )
        return f"content:{context_name}"

    # ------------------------------------------------------------------
    # Dynamic autocomplete hooks
    # ------------------------------------------------------------------
    def supports_autocomplete(self) -> bool:
        return True

    def autocomplete(self, fragment: str, max_results: int = 10) -> List[str]:
        """Return up to *max_results* full-path suggestions whose basename
        contains the fragment substring (case-insensitive)."""
        # Determine the actual search term depending on which prefix we see.
        if fragment.lower().startswith(self.PREFIX_REF):
            search_term = fragment[len(self.PREFIX_REF) :].lower()
        else:
            # Generic "@" case – remove just the leading '@'
            search_term = fragment[1:].lower()

        # Bail out early unless the user typed at least *MIN_CHARS* chars
        # (excluding the leading '@').  This prevents the file index from
        # showing up too aggressively and ensures that built-in tags and
        # user shortcuts are presented first for short fragments.
        if len(search_term) < self.MIN_CHARS:
            return []

        if not search_term:
            return []

        matches = [fp for base, fp in self._index if search_term in base]
        matches.sort()  # alphabetical by full path

        # Build raw tag strings – always include the @file prefix so that our
        # plugin is invoked during expansion.  Quote the path so we have a
        # clear separator after the prefix and we don't need special handling
        # for leading slashes.
        raw_tags: list[str] = []
        for p in matches[:max_results]:
            # Insert as a *plain* path tag so the user sees @"/path".  Quotes
            # are used to keep the path intact if it contains spaces.
            raw_tags.append(f'@"{p}"')
        return raw_tags

    def display_string(self, suggestion: str) -> str:
        # Handle both internal @file"…" variants and plain path tags.
        if suggestion.startswith(self.PREFIX_REF):
            path_spec = suggestion[len(self.PREFIX_REF) :]
        elif suggestion.startswith('@'):
            path_spec = suggestion[1:]
        else:
            return suggestion

        if path_spec.startswith('"') and path_spec.endswith('"'):
            path_spec = path_spec[1:-1]
        return Path(path_spec).name

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