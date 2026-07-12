"""Virtual filesystem mounts, resolution, and workspace lifecycle."""

from __future__ import annotations

import os
import posixpath
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from macllm.core.config import get_runtime_config
from macllm.core.context import get_current_conversation
from macllm.core.sandbox import ALWAYS_DENIED_PATHS
from macllm.core.storage import get_storage_dir

FILESYSTEM_MAX_AGE = 7 * 24 * 60 * 60


class FilesystemError(ValueError):
    pass


@dataclass
class Mount:
    name: str
    virtual: str
    host: Path | None
    supervisor_access: str
    subagent_access: str
    index: bool = False
    root_must_exist: bool = False

    def access(self, restricted: bool) -> str:
        return self.subagent_access if restricted else self.supervisor_access


@dataclass
class ResolvedPath:
    virtual: str
    mount: Mount
    path: Path
    canonical: Path


def filesystems_dir() -> Path:
    return get_storage_dir() / "filesystems"


def conversation_root(conversation) -> Path:
    return filesystems_dir() / conversation.conv_id


def create_conversation_root(conversation) -> Path:
    root = conversation_root(conversation)
    root.mkdir(parents=True)
    (root / "home").mkdir()
    return root


def _creation_time(path: Path) -> float:
    stat = path.stat()
    return getattr(stat, "st_birthtime", stat.st_mtime)


def garbage_collect_filesystems(max_age: float = FILESYSTEM_MAX_AGE) -> None:
    base = filesystems_dir()
    if not base.exists():
        return
    cutoff = time.time() - max_age
    for root in base.iterdir():
        try:
            if root.is_dir() and _creation_time(root) < cutoff:
                shutil.rmtree(root)
        except OSError:
            continue


def _normalise(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise FilesystemError("Path must be an absolute virtual path beginning with '/'.")
    return "/" + posixpath.normpath(path).lstrip("/")


def _contains(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        return False


def _restricted(conversation) -> bool:
    return bool(getattr(conversation.current_agent, "read_only_no_hostfs", False))


def configured_mounts() -> list[Mount]:
    return [
        Mount(
            name=name,
            virtual=_normalise(config.virtual),
            host=Path(config.path),
            supervisor_access=config.supervisor_access,
            subagent_access=config.subagent_access,
            index=config.index,
        )
        for name, config in get_runtime_config().resolved_filesystem_mounts().items()
    ]


def _runtime_mounts(conversation) -> list[Mount]:
    mounts = [
        Mount(
            "home",
            "/home",
            conversation_root(conversation) / "home",
            "read-write",
            "read-write",
            root_must_exist=True,
        ),
        Mount("host", "/host", None, "read-only", "none"),
    ]
    for granted in conversation.get_granted_dirs():
        host = Path(granted).expanduser().resolve(strict=False)
        mounts.append(
            Mount(
                f"host:{host}",
                _normalise(f"/host{host}"),
                host,
                "read-write",
                "none",
            )
        )
    return mounts


class MountTable:
    def __init__(self, conversation):
        self.conversation = conversation
        self.mounts = configured_mounts() + _runtime_mounts(conversation)

    def find(self, virtual: str) -> Mount | None:
        matches = [
            mount
            for mount in self.mounts
            if virtual == mount.virtual or virtual.startswith(mount.virtual + "/")
        ]
        return max(matches, key=lambda mount: len(mount.virtual), default=None)

    def children(self, virtual: str) -> list[str] | None:
        prefix = "/" if virtual == "/" else virtual + "/"
        children = set()
        restricted = _restricted(self.conversation)
        virtual_directory = False
        for mount in self.mounts:
            if mount.access(restricted) == "none":
                continue
            if mount.virtual == virtual and mount.host is None:
                virtual_directory = True
            if not mount.virtual.startswith(prefix):
                continue
            remainder = mount.virtual[len(prefix):]
            if remainder:
                children.add(remainder.split("/", 1)[0] + "/")
        if children or virtual_directory:
            return sorted(children)
        return None


def _host_to_virtual(
    source: str,
    mounts: list[Mount],
    *,
    resolve_symlinks: bool = True,
) -> str | None:
    source_path = (
        Path(source).resolve(strict=False)
        if resolve_symlinks
        else Path(source).absolute()
    )
    matches = []
    for mount in mounts:
        if mount.host is None:
            continue
        root = (
            mount.host.resolve(strict=False)
            if resolve_symlinks
            else mount.host.absolute()
        )
        if _contains(root, source_path):
            matches.append((len(str(root)), mount, root))
    if not matches:
        return None
    _, mount, root = max(matches, key=lambda match: match[0])
    relative = source_path.relative_to(root).as_posix()
    return mount.virtual if relative == "." else f"{mount.virtual}/{relative}"


def skill_virtual_path(source: str) -> str | None:
    mounts = [
        mount
        for mount in configured_mounts()
        if mount.virtual == "/skills" or mount.virtual.startswith("/skills/")
    ]
    return _host_to_virtual(source, mounts, resolve_symlinks=False)


def indexed_virtual_path(source: str) -> str | None:
    return _host_to_virtual(source, indexed_mounts())


def is_configured_virtual_path(path: str) -> bool:
    virtual = _normalise(path)
    return any(
        virtual == mount.virtual or virtual.startswith(mount.virtual + "/")
        for mount in configured_mounts()
    )


def indexed_mounts() -> list[Mount]:
    return [mount for mount in configured_mounts() if mount.index]


def _check_access(mount: Mount, write: bool, conversation) -> None:
    access = mount.access(_restricted(conversation))
    if access == "none" or (write and access != "read-write"):
        operation = "write to" if write else "read"
        raise FilesystemError(f"Current agent may not {operation} '{mount.virtual}'.")


def _check_denied_host_path(mount: Mount, candidate: Path) -> None:
    if not mount.virtual.startswith("/host"):
        return
    denied = [Path(path).expanduser().resolve(strict=False) for path in ALWAYS_DENIED_PATHS]
    if any(_contains(root, candidate) for root in denied):
        raise FilesystemError(f"Host path '{candidate}' is always denied.")


def resolve_path(
    path: str,
    *,
    write: bool = False,
    conversation=None,
    deleting: bool = False,
) -> ResolvedPath:
    conversation = conversation or get_current_conversation()
    if conversation is None:
        raise FilesystemError("No active conversation.")

    virtual = _normalise(path)
    mount = MountTable(conversation).find(virtual)
    if mount is None:
        raise FilesystemError(f"Path '{virtual}' is not mounted.")
    _check_access(mount, write, conversation)
    if mount.host is None:
        raise FilesystemError(f"Host path '{virtual[5:] or '/'}' requires user permission.")
    if mount.root_must_exist and (
        mount.host.is_symlink() or not mount.host.is_dir()
    ):
        raise FilesystemError(f"Filesystem root '{mount.virtual}' is missing or invalid.")

    relative = virtual[len(mount.virtual):].lstrip("/")
    lexical = mount.host / relative
    root = mount.host.resolve(strict=False)
    parent = lexical.parent.resolve(strict=False)
    skill_symlink_read = (
        not write
        and (
            mount.virtual == "/skills"
            or mount.virtual.startswith("/skills/")
        )
    )
    if lexical != mount.host and not skill_symlink_read and not _contains(root, parent):
        raise FilesystemError(f"Path '{virtual}' escapes its mount.")

    canonical = lexical.resolve(strict=False)
    if (
        not skill_symlink_read
        and not (deleting and lexical.is_symlink())
        and not _contains(root, canonical)
    ):
        raise FilesystemError(f"Path '{virtual}' escapes its mount through a symlink.")
    checked = parent / lexical.name if deleting and lexical.is_symlink() else canonical
    _check_denied_host_path(mount, checked)
    return ResolvedPath(virtual, mount, lexical, canonical)


def list_virtual_directory(path: str, conversation=None) -> list[str] | None:
    conversation = conversation or get_current_conversation()
    if conversation is None:
        raise FilesystemError("No active conversation.")
    virtual = _normalise(path)
    return MountTable(conversation).children(virtual)
