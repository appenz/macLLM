import time
from types import SimpleNamespace

import pytest

from macllm.core import config as config_mod
from macllm.core.chat_history import Conversation
from macllm.core.config import (
    FilesystemConfig,
    FilesystemMountConfig,
    MacLLMConfig,
    ShellConfig,
)
from macllm.core.context import set_current_conversation
from macllm.core.virtual_filesystem import (
    FilesystemError,
    conversation_root,
    create_conversation_root,
    garbage_collect_filesystems,
    indexed_virtual_path,
    resolve_path,
)


@pytest.fixture
def filesystem_env(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    memory = tmp_path / "memory"
    skills = tmp_path / "skills"
    host = tmp_path / "host"
    for path in (notes, memory, skills, host):
        path.mkdir()
    cfg = MacLLMConfig(
        filesystem=FilesystemConfig({
            "Notes": FilesystemMountConfig(
                "/notes/Notes", str(notes), "read-write", "read-only", True
            ),
            "memory": FilesystemMountConfig(
                "/memory", str(memory), "read-write", "read-only", False
            ),
            "skills": FilesystemMountConfig(
                "/skills/skills", str(skills), "read-only", "read-only", False
            ),
        }),
        shell=ShellConfig(default_dirs=[str(host)]),
    )
    monkeypatch.setattr(config_mod, "_RUNTIME_CONFIG", cfg)
    monkeypatch.setattr(
        "macllm.core.virtual_filesystem.get_storage_dir", lambda: tmp_path / "app"
    )
    conv = Conversation()
    create_conversation_root(conv)
    set_current_conversation(conv)
    yield conv, notes, memory, skills, host, tmp_path / "app"
    set_current_conversation(None)


def test_normalises_before_selecting_mount(filesystem_env):
    _, notes, *_ = filesystem_env
    resolved = resolve_path("/notes/Notes/folder/../file.md")
    assert resolved.path == notes / "file.md"


def test_indexed_host_path_maps_to_virtual_path(filesystem_env):
    _, notes, *_ = filesystem_env
    assert indexed_virtual_path(str(notes / "folder" / "file.md")) == (
        "/notes/Notes/folder/file.md"
    )


def test_symlink_cannot_escape_mount(filesystem_env):
    _, notes, _, _, host, _ = filesystem_env
    (notes / "escape").symlink_to(host, target_is_directory=True)
    with pytest.raises(FilesystemError, match="escapes its mount"):
        resolve_path("/notes/Notes/escape/file.md")


def test_subagent_permissions(filesystem_env):
    conversation, *_ = filesystem_env
    conversation.current_agent = SimpleNamespace(read_only_no_hostfs=True)
    try:
        assert resolve_path("/notes/Notes/file.md").mount.name == "Notes"
        assert resolve_path("/home/output.md", write=True).mount.name == "home"
        with pytest.raises(FilesystemError, match="may not write"):
            resolve_path("/memory/output.md", write=True)
        with pytest.raises(FilesystemError, match="/host"):
            resolve_path("/host/tmp/file.md")
        with pytest.raises(FilesystemError, match="/host"):
            resolve_path("/notes/../host/tmp/file.md")
    finally:
        conversation.current_agent = None


def test_parent_host_requires_grant(filesystem_env):
    _, _, _, _, host, _ = filesystem_env
    assert resolve_path(f"/host{host}/file.md").mount.name.startswith("host:")
    with pytest.raises(FilesystemError, match="requires user permission"):
        resolve_path("/host/private/file.md")


def test_home_is_conversation_private(filesystem_env):
    first, *_ = filesystem_env
    first_home = resolve_path("/home/file.md", conversation=first).path
    second = Conversation()
    create_conversation_root(second)
    second_home = resolve_path("/home/file.md", conversation=second).path
    assert first_home != second_home


def test_missing_home_is_not_recreated(filesystem_env):
    conversation, *_ = filesystem_env
    (conversation_root(conversation) / "home").rmdir()

    with pytest.raises(FilesystemError, match="missing or invalid"):
        resolve_path("/home/file.md", conversation=conversation)

    assert not (conversation_root(conversation) / "home").exists()


def test_startup_gc_uses_root_creation_date(filesystem_env, monkeypatch):
    conv, *_, app = filesystem_env
    old = conversation_root(conv)
    stale = time.time() - 8 * 24 * 60 * 60
    recent = app / "filesystems" / "recent"
    (recent / "home").mkdir(parents=True)
    monkeypatch.setattr(
        "macllm.core.virtual_filesystem._creation_time",
        lambda path: stale if path == old else time.time(),
    )

    garbage_collect_filesystems()

    assert not old.exists()
    assert recent.exists()
