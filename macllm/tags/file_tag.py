from __future__ import annotations

import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

import json
import threading
from pathlib import Path
from typing import List, Optional

import txtai

from macllm.core.model_paths import get_embedding_model_dir
from macllm.core.virtual_filesystem import (
    indexed_mounts,
    indexed_virtual_path,
    is_configured_virtual_path,
)

from .base import TagPlugin


class FileTag(TagPlugin):
    """Index configured files and expand path tags into filesystem references."""

    # Public constants
    PREFIX_REINDEX = "/reindex"

    # Prefixes that represent plain path tags (previously handled by PathTag)
    PATH_PREFIXES = ["@/", "@~", "@\"/", "@\"~"]

    DIR_SHORTCUTS = {
        "@home": "~/",
        "@desktop": "~/Desktop/",
        "@downloads": "~/Downloads/",
        "@documents": "~/Documents/",
    }

    # Also allow generic "@" prefix for autocomplete (without explicit keyword)
    # Autocomplete suggestions will only be generated once the user has typed
    # at least *MIN_CHARS* characters after the leading "@".
    MIN_CHARS = 3
    EXTENSIONS = (".txt", ".md")
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff", ".bmp")
    MAX_CONTEXT_LEN = 200 * 1024  # cap identical to old PathTag
    MAX_FULL_FILE_LEN = 10 * 1000
    SEARCH_PREVIEW_LEN = 1000
    SEARCH_RESULTS_COUNT = 5

    REINDEX_INTERVAL = 5 * 60  # seconds between periodic re-indexes
    CACHE_SUBDIR = "embeddings-local-v1"

    # Class-level state for file index and embeddings
    _macllm = None
    _index: list[tuple[str, str]] = []
    _indexed_directories: list[str] = []
    _embeddings: Optional[txtai.Embeddings] = None
    _embedding_ready = threading.Event()
    _embedding_lock = threading.Lock()
    _reindex_event = threading.Event()
    _file_mtimes: dict[str, float] = {}
    _filepath_to_idx: dict[str, int] = {}
    _first_build_done: bool = False

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
        FileTag._file_mtimes = {}
        FileTag._filepath_to_idx = {}
        FileTag._first_build_done = False

    @classmethod
    def _debug_log(cls, message: str, level: int = 0) -> None:
        if cls._macllm is not None:
            cls._macllm.debug_log(message, level)

    @classmethod
    def build_index(cls):
        """Walk all indexed directories and build the file index."""
        cls._index = []
        cls._indexed_directories = [
            str(mount.host)
            for mount in indexed_mounts()
            if mount.host is not None and mount.host.is_dir()
        ]
        for dir_path in cls._indexed_directories:
            for fp in Path(dir_path).rglob("*"):
                if fp.is_file() and fp.suffix.lower() in cls.EXTENSIONS:
                    cls._index.append((fp.name.lower(), str(fp)))

        # Sort alphabetically by basename for deterministic ordering
        cls._index.sort(key=lambda t: t[0])
        cls._filepath_to_idx = {fp: idx for idx, (_, fp) in enumerate(cls._index)}

    # ------------------------------------------------------------------
    # TagPlugin interface – normal expansion
    # ------------------------------------------------------------------
    def get_prefixes(self) -> List[str]:
        # We now own *all* path-like tags.  Return only prefixes that should
        # trigger *expansion*.  The generic "@" is **excluded** here so that
        # other plugins (e.g. ClipboardTag) are not shadowed during
        # expansion.  We still use the generic symbol for autocomplete via
        # *match_any_autocomplete()*.
        return self.PATH_PREFIXES + list(self.DIR_SHORTCUTS.keys()) + [self.PREFIX_REINDEX]

    # ------------------------------------------------------------------
    # Catch-all autocomplete flag
    # ------------------------------------------------------------------
    def match_any_autocomplete(self) -> bool:  # noqa: D401
        """Indicate that this plugin wants to be queried for autocomplete
        suggestions for *all* "@…" fragments, regardless of prefix match."""
        return True

    def expand(self, tag: str, conversation, request):
        """Rewrite path tags into tool instructions; grant directories for tools.

        For files: preserve the path and tell the model to call ``read_file``.
        For directories / shortcuts: grant sandbox access and mention the path.
        Never reads file contents or loads images.
        """

        if tag == self.PREFIX_REINDEX:
            FileTag._start_reindex()
            return ""

        # Handle directory shortcuts (@home, @desktop, etc.)
        tag_lower = tag.lower()
        for shortcut, shortcut_path in self.DIR_SHORTCUTS.items():
            if tag_lower == shortcut:
                expanded_path = os.path.expanduser(shortcut_path)
                conversation.grant_directory(expanded_path)
                return f"Directory /host{expanded_path} (access granted)"

        # Only handle tags that use one of our path prefixes.
        if any(tag.startswith(p) for p in self.PATH_PREFIXES):
            path_spec = tag[1:]
        else:
            return tag

        if path_spec.startswith('"') and path_spec.endswith('"'):
            path_spec = path_spec[1:-1]

        path_spec = os.path.expanduser(path_spec)

        if is_configured_virtual_path(path_spec):
            return f'{path_spec} (use read_file("{path_spec}") to read)'

        if os.path.isdir(path_spec):
            conversation.grant_directory(path_spec)
            return f"Directory /host{path_spec} (access granted)"

        # Grant the parent directory so read_file / shell can access the file.
        parent = os.path.dirname(os.path.abspath(path_spec))
        if parent:
            conversation.grant_directory(parent)

        virtual = f"/host{os.path.abspath(path_spec)}"
        return f'{virtual} (use read_file("{virtual}") to read)'

    # ------------------------------------------------------------------
    # Dynamic autocomplete hooks
    # ------------------------------------------------------------------
    def supports_autocomplete(self) -> bool:
        return True

    def autocomplete(self, fragment: str, max_results: int = 10) -> List[str]:
        """Return suggestions for *fragment* using either live filesystem
        exploration, directory shortcuts, or the pre-built index."""

        # Path-style fragments are handled via live filesystem completion without
        # applying the *MIN_CHARS* limit so that patterns like "@/" start
        # suggesting immediately.
        if any(fragment.startswith(p) for p in self.PATH_PREFIXES):
            return self._autocomplete_live_path(fragment, max_results)

        # Match directory shortcuts (@home, @desktop, etc.)
        frag_lower = fragment.lower()
        shortcut_matches = [
            sc for sc in self.DIR_SHORTCUTS if sc.startswith(frag_lower)
        ]
        if shortcut_matches:
            return shortcut_matches[:max_results]

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
            virtual = indexed_virtual_path(p)
            if virtual is not None:
                raw_tags.append(f'@"{virtual}"')
        return raw_tags

    def display_string(self, suggestion: str) -> str:
        if suggestion in self.DIR_SHORTCUTS:
            return "📂" + suggestion[1:]

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
        """Start a daemon thread that periodically rebuilds the file index.

        Embeddings are initialized lazily by semantic search so normal app
        startup does not load model weights.
        """
        if interval is None:
            interval = cls.REINDEX_INTERVAL
        thread = threading.Thread(target=cls._index_loop, args=(interval,), daemon=True, name="FileTagIndexLoop")
        thread.start()

    @classmethod
    def _index_loop(cls, interval: float):
        while True:
            cls.build_index()
            if cls._index and (cls._embeddings is not None or cls._first_build_done):
                cls._build_embeddings()
            cls._reindex_event.wait(timeout=interval)
            cls._reindex_event.clear()

    @classmethod
    def _start_reindex(cls):
        cls._debug_log("Reindexing...", 0)
        cls._reindex_event.set()

    @classmethod
    def _load_embedding_model(cls) -> txtai.Embeddings:
        """Load embeddings from the app-managed local model snapshot only."""
        return txtai.Embeddings(path=str(get_embedding_model_dir()))

    @classmethod
    def _cache_dir(cls) -> Path:
        from macllm.core.persistence import get_storage_dir
        return get_storage_dir() / cls.CACHE_SUBDIR

    @classmethod
    def _save_cache(cls):
        try:
            cache_dir = cls._cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            with cls._embedding_lock:
                if cls._embeddings is not None:
                    cls._embeddings.save(str(cache_dir))
            with open(cache_dir / "mtimes.json", "w") as f:
                json.dump(cls._file_mtimes, f)
        except Exception as e:
            if cls._macllm:
                cls._debug_log(f"Failed to save embedding cache: {e}", 1)

    @classmethod
    def _load_cache(cls) -> bool:
        """Attempt to restore embeddings from disk cache.

        Returns ``True`` if the cache was loaded successfully, populating
        ``_embeddings``, ``_file_mtimes``, and setting ``_first_build_done``.
        On any failure the state is left clean so a full rebuild can proceed.
        """
        cache_dir = cls._cache_dir()
        mtimes_path = cache_dir / "mtimes.json"
        if not mtimes_path.exists():
            return False
        try:
            with open(mtimes_path, "r") as f:
                cls._file_mtimes = json.load(f)
            embeddings = cls._load_embedding_model()
            embeddings.load(str(cache_dir))
            cls._embeddings = embeddings
            cls._first_build_done = True
            cls._debug_log(
                f"Loaded embedding cache ({len(cls._file_mtimes)} files)", 0
            )
            return True
        except Exception as e:
            cls._debug_log(f"Cache load failed, rebuilding: {e}", 1)
            cls._file_mtimes = {}
            cls._embeddings = None
            cls._first_build_done = False
            return False

    @classmethod
    def _prepare_docs(cls, filepaths: list[str]) -> list[tuple]:
        """Build txtai document tuples for the given filepaths.

        Each tuple is ``(filepath, indexed_content, None)`` where *filepath*
        is used as a stable document ID.
        """
        docs = []
        for filepath in filepaths:
            try:
                filename = Path(filepath).name
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read(cls.SEARCH_PREVIEW_LEN)
                indexed_content = f"{filename}\n{content}"
                docs.append((filepath, indexed_content, None))
            except Exception as e:
                cls._debug_log(f"Skipping unreadable file: {filepath} ({e})", 1)
        return docs

    @classmethod
    def _build_embeddings(cls):
        if not cls._first_build_done:
            cls._load_cache()

        current_mtimes: dict[str, float] = {}
        for _, filepath in cls._index:
            try:
                current_mtimes[filepath] = os.path.getmtime(filepath)
            except OSError:
                continue

        new_files = [fp for fp in current_mtimes if fp not in cls._file_mtimes]
        changed_files = [
            fp for fp in current_mtimes
            if fp in cls._file_mtimes and cls._file_mtimes[fp] != current_mtimes[fp]
        ]
        deleted_files = [fp for fp in cls._file_mtimes if fp not in current_mtimes]

        if not new_files and not changed_files and not deleted_files and cls._first_build_done:
            cls._embedding_ready.set()
            return

        n_new, n_changed, n_deleted = len(new_files), len(changed_files), len(deleted_files)
        n_unchanged = len(current_mtimes) - n_new - n_changed
        cls._debug_log(
            f"Embedding update: {n_new} new, {n_changed} changed, "
            f"{n_deleted} deleted, {n_unchanged} unchanged",
            0,
        )

        with cls._embedding_lock:
            if cls._embeddings is None:
                cls._embeddings = cls._load_embedding_model()

            if not cls._first_build_done:
                docs = cls._prepare_docs(list(current_mtimes.keys()))
                if docs:
                    cls._embeddings.index(docs)
                cls._first_build_done = True
            else:
                if deleted_files:
                    cls._embeddings.delete(deleted_files)
                files_to_upsert = new_files + changed_files
                if files_to_upsert:
                    docs = cls._prepare_docs(files_to_upsert)
                    if docs:
                        cls._embeddings.upsert(docs)

        cls._file_mtimes = current_mtimes
        cls._embedding_ready.set()
        cls._save_cache()

    @classmethod
    def search(cls, query: str, n: int = SEARCH_RESULTS_COUNT, timeout: float = 60.0) -> list[tuple[int, float, str, str, bool]]:
        if not cls._index:
            cls.build_index()

        if not cls._index:
            return []

        if cls._embeddings is None:
            cls._embedding_ready.clear()
            cls._build_embeddings()
        elif not cls._embedding_ready.wait(timeout=timeout):
            return []

        with cls._embedding_lock:
            if cls._embeddings is None:
                return []
            results = cls._embeddings.search(query, n)

        output = []
        for doc_id, score in results:
            if isinstance(doc_id, str):
                filepath = doc_id
            elif 0 <= doc_id < len(cls._index):
                filepath = cls._index[doc_id][1]
            else:
                continue
            idx = cls._filepath_to_idx.get(filepath)
            if idx is None:
                continue
            truncated = False
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    preview = f.read(cls.SEARCH_PREVIEW_LEN)
                    truncated = f.read(1) != ""
            except Exception:
                preview = "(unable to read file)"
            output.append((idx, score, filepath, preview, truncated))
        return output

    @classmethod
    def get_file_content(cls, file_id: int) -> tuple[str, str]:
        if file_id < 0 or file_id >= len(cls._index):
            raise IndexError(f"Invalid file ID: {file_id}")
        _, filepath = cls._index[file_id]
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(cls.MAX_FULL_FILE_LEN)
        return content, filepath
