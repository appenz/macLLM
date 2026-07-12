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
from macllm.core.virtual_filesystem import create_conversation_root
from macllm.tags.file_tag import FileTag


@pytest.fixture
def filesystem_env(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    memory = tmp_path / "memory"
    skills = tmp_path / "skills"
    host = tmp_path / "host"
    for path in (notes, memory, skills, host):
        path.mkdir()
    (notes / "input.md").write_text("notes input")
    (skills / "SKILL.md").write_text("skill instructions")
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
    FileTag._indexed_directories = [str(notes)]
    conv = Conversation()
    create_conversation_root(conv)
    set_current_conversation(conv)
    yield conv, notes, memory, skills, host
    set_current_conversation(None)
    FileTag._indexed_directories = []


def test_home_file_lifecycle(filesystem_env):
    from macllm.tools import filesystem as fs

    assert fs.create_directory.forward("/home/output") == "Created /home/output"
    assert fs.write_file.forward("/home/output/result.md", "one") == (
        "Wrote /home/output/result.md"
    )
    assert fs.append_file.forward("/home/output/result.md", " two") == (
        "Appended to /home/output/result.md"
    )
    assert fs.read_file.forward("/home/output/result.md") == "one two"
    assert "result.md" in fs.list_directory.forward("/home/output")
    assert fs.copy_file.forward(
        "/home/output/result.md", "/home/output/copy.md"
    ) == "Copied /home/output/result.md to /home/output/copy.md"
    assert fs.delete_file.forward("/home/output/copy.md") == (
        "Deleted /home/output/copy.md"
    )


def test_create_directory_requires_existing_parent(filesystem_env):
    from macllm.tools import filesystem as fs

    result = fs.create_directory.forward("/home/missing/child")
    assert "Parent directory does not exist" in result


def test_directory_delete_requires_recursive(filesystem_env):
    from macllm.tools import filesystem as fs

    fs.create_directory.forward("/home/folder")
    assert "recursive=True" in fs.delete_file.forward("/home/folder")
    assert fs.delete_file.forward("/home/folder", recursive=True) == (
        "Deleted /home/folder"
    )


def test_subagent_reads_shared_mounts_but_writes_only_home(filesystem_env):
    from macllm.tools import filesystem as fs

    conversation, *_ = filesystem_env
    conversation.current_agent = SimpleNamespace(read_only_no_hostfs=True)
    try:
        assert fs.read_file.forward("/notes/Notes/input.md") == "notes input"
        assert fs.read_file.forward("/skills/skills/SKILL.md") == (
            "skill instructions"
        )
        assert fs.write_file.forward("/home/output.md", "ok") == "Wrote /home/output.md"
        assert "may not write" in fs.write_file.forward("/memory/output.md", "no")
    finally:
        conversation.current_agent = None


def test_parent_can_write_memory_and_granted_host(filesystem_env):
    from macllm.tools import filesystem as fs

    _, _, memory, _, host = filesystem_env
    assert fs.write_file.forward("/memory/fact.md", "fact") == "Wrote /memory/fact.md"
    assert memory.joinpath("fact.md").read_text() == "fact"
    virtual_host = f"/host{host}/artifact.md"
    assert fs.write_file.forward(virtual_host, "artifact") == f"Wrote {virtual_host}"
    assert host.joinpath("artifact.md").read_text() == "artifact"


def test_copy_from_notes_to_subagent_home(filesystem_env):
    from macllm.tools import filesystem as fs

    conversation, *_ = filesystem_env
    conversation.current_agent = SimpleNamespace(read_only_no_hostfs=True)
    try:
        assert fs.copy_file.forward("/notes/Notes/input.md", "/home/input.md") == (
            "Copied /notes/Notes/input.md to /home/input.md"
        )
    finally:
        conversation.current_agent = None
