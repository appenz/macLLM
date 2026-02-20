from __future__ import annotations

import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

import threading
from pathlib import Path
from typing import List, Optional

import txtai

from .base import TagPlugin


class FileTag(TagPlugin):
    """Handle directory indexing via *config tag* `@IndexFiles` and expose
    `@file` tag that lets the user embed the contents of an indexed file.
    """

    # Public constants
    PREFIX_CONFIG = "@IndexFiles"
    PREFIX_REINDEX = "/reindex"

    # Prefixes that represent plain path tags (previously handled by PathTag)
    PATH_PREFIXES = ["@/", "@~", "@\"/", "@\"~"]

    # Also allow generic "@" prefix for autocomplete (without explicit keyword)
    # Autocomplete suggestions will only be generated once the user has typed
    # at least *MIN_CHARS* characters after the leading "@".
    MIN_CHARS = 3
    EXTENSIONS = (".txt", ".md")
    MAX_CONTEXT_LEN = 10 * 1024  # 10 KB cap identical to old PathTag
    MAX_FULL_FILE_LEN = 10 * 1000
    SEARCH_PREVIEW_LEN = 1000
    SEARCH_RESULTS_COUNT = 5

    REINDEX_INTERVAL = 5 * 60  # seconds between periodic re-indexes

    # Class-level state for file index and embeddings
    _macllm = None
    _index: list[tuple[str, str]] = []
    _indexed_directories: list[str] = []
    _embeddings: Optional[txtai.Embeddings] = None
    _embedding_ready = threading.Event()
    _embedding_lock = threading.Lock()
    _reindex_event = threading.Event()

    # ------------------------------------------------------------------
    # Object lifecycle
    # ------------------------------------------------------------------
    def __init__(self, macllm):
        super().__init__(macllm)
        FileTag._macllm = macllm
        FileTag._index = []
        FileTag._indexed_directories = []
        FileTag._embeddings = None
        FileTag._embedding_ready = threading.Event()
        FileTag._reindex_event = threading.Event()

    # ------------------------------------------------------------------
    # TagPlugin interface – configuration tags
    # ------------------------------------------------------------------
    def get_config_prefixes(self) -> List[str]:
        return [self.PREFIX_CONFIG]

    def on_config_tag(self, tag: str, value: str):  # noqa: D401
        """Called during shortcut loading for each `@IndexFiles` entry.

        *value* is expected to be a path string. We collect the directory
        for later indexing via build_index()."""
        dir_path = value.strip().strip('"')
        dir_path = os.path.expandvars(os.path.expanduser(dir_path))

        if os.path.isdir(dir_path) is False:
            FileTag._macllm.debug_log(f"@IndexFiles: Not a directory – {dir_path}", 2)
            return

        # Collect directory for later indexing
        if dir_path not in FileTag._indexed_directories:
            FileTag._indexed_directories.append(dir_path)

    @classmethod
    def build_index(cls):
        """Walk all indexed directories and build the file index."""
        cls._index = []
        for dir_path in cls._indexed_directories:
            for fp in Path(dir_path).rglob("*"):
                if fp.is_file() and fp.suffix.lower() in cls.EXTENSIONS:
                    cls._index.append((fp.name.lower(), str(fp)))

        # Sort alphabetically by basename for deterministic ordering
        cls._index.sort(key=lambda t: t[0])
        if cls._macllm:
            cls._macllm.debug_log(f"Indexed {len(cls._index)} files from {len(cls._indexed_directories)} directories", 0)

    # ------------------------------------------------------------------
    # TagPlugin interface – normal expansion
    # ------------------------------------------------------------------
    def get_prefixes(self) -> List[str]:
        # We now own *all* path-like tags.  Return only prefixes that should
        # trigger *expansion*.  The generic "@" is **excluded** here so that
        # other plugins (e.g. ClipboardTag) are not shadowed during
        # expansion.  We still use the generic symbol for autocomplete via
        # *match_any_autocomplete()*.
        return self.PATH_PREFIXES + [self.PREFIX_REINDEX]

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
        ``context:<handle>`` replacement string."""

        if tag == self.PREFIX_REINDEX:
            FileTag._start_reindex()
            return ""

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
        except Exception as exc:
            FileTag._macllm.debug_exception(exc)
            return tag  # leave unmodified so the user sees the failure

        context_name = conversation.add_context(
            Path(path_spec).name,
            path_spec,
            "path",
            content,
            icon="📁"
        )
        return f"\n\n--- context:{context_name} (path: {path_spec}) ---\n{content}\n--- end context:{context_name} ---"

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
        matches = [fp for base, fp in FileTag._index if term_lc in base]
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

    # ------------------------------------------------------------------
    # Embedding search (class methods)
    # ------------------------------------------------------------------
    @classmethod
    def start_index_loop(cls, interval: float = None):
        """Start a daemon thread that periodically rebuilds the file index
        and embeddings.  The first cycle runs immediately."""
        if interval is None:
            interval = cls.REINDEX_INTERVAL
        thread = threading.Thread(target=cls._index_loop, args=(interval,), daemon=True)
        thread.start()

    @classmethod
    def _index_loop(cls, interval: float):
        while True:
            cls.build_index()
            if cls._index:
                cls._build_embeddings()
            else:
                cls._embedding_ready.set()
            cls._reindex_event.wait(timeout=interval)
            cls._reindex_event.clear()

    @classmethod
    def _start_reindex(cls):
        cls._macllm.debug_log("Reindexing...", 0)
        cls._reindex_event.set()

    @classmethod
    def _load_embedding_model(cls) -> txtai.Embeddings:
        """Load the sentence-transformer model.

        Attempts one normal load (which may check for updates or download the
        model on the very first run).  If that fails (e.g. network is down),
        retries in offline/cache-only mode.  After loading, locks the process
        to offline so the periodic reindex never triggers network requests.
        """
        model_path = "sentence-transformers/all-mpnet-base-v2"
        try:
            embeddings = txtai.Embeddings(path=model_path)
        except Exception:
            os.environ["HF_HUB_OFFLINE"] = "1"
            embeddings = txtai.Embeddings(path=model_path)
        os.environ["HF_HUB_OFFLINE"] = "1"
        return embeddings

    @classmethod
    def _build_embeddings(cls):
        cls._macllm.debug_log(f"Building embeddings for {len(cls._index)} files...", 0)

        docs = []
        for idx, (_, filepath) in enumerate(cls._index):
            try:
                filename = Path(filepath).name
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read(cls.SEARCH_PREVIEW_LEN)
                # Prepend filename to content so it's searchable
                indexed_content = f"{filename}\n{content}"
                docs.append((idx, indexed_content, filepath))
            except Exception as e:
                # Skip files that can't be read - no point indexing them if content is unavailable
                cls._macllm.debug_log(f"Skipping unreadable file: {filepath} ({e})", 1)
                continue

        with cls._embedding_lock:
            if cls._embeddings is None:
                cls._embeddings = cls._load_embedding_model()
            cls._embeddings.index(docs)

        cls._embedding_ready.set()
        cls._macllm.debug_log("Embedding build complete", 0)

    @classmethod
    def search(cls, query: str, n: int = SEARCH_RESULTS_COUNT, timeout: float = 60.0) -> list[tuple[int, float, str, str, bool]]:
        if not cls._embedding_ready.wait(timeout=timeout):
            return []

        with cls._embedding_lock:
            if cls._embeddings is None:
                return []
            results = cls._embeddings.search(query, n)

        output = []
        for doc_id, score in results:
            if doc_id < 0 or doc_id >= len(cls._index):
                continue
            _, filepath = cls._index[doc_id]
            truncated = False
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    preview = f.read(cls.SEARCH_PREVIEW_LEN)
                    truncated = f.read(1) != ""
            except Exception:
                preview = "(unable to read file)"
            output.append((doc_id, score, filepath, preview, truncated))
        return output

    @classmethod
    def get_file_content(cls, file_id: int) -> tuple[str, str]:
        if file_id < 0 or file_id >= len(cls._index):
            raise IndexError(f"Invalid file ID: {file_id}")
        _, filepath = cls._index[file_id]
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(cls.MAX_FULL_FILE_LEN)
        return content, filepath
