"""Tests for direct-read tools and image observation bridging."""

from unittest.mock import Mock

import pytest
from PIL import Image

from macllm.core.chat_history import Conversation
from macllm.core.context import set_current_conversation, _thread_context
from macllm.tags.file_tag import FileTag


@pytest.fixture(autouse=True)
def _clean_tool_context():
    prev_dirs = list(FileTag._indexed_directories)
    prev_mounts = dict(FileTag._mount_points)
    prev_conv = getattr(_thread_context, "conversation", None)
    try:
        yield
    finally:
        FileTag._indexed_directories = prev_dirs
        FileTag._mount_points = prev_mounts
        _thread_context.conversation = prev_conv


def test_read_clipboard_text(monkeypatch):
    from macllm.tools import clipboard as clipboard_mod

    conv = Conversation()
    set_current_conversation(conv)

    ui = Mock()
    ui.read_clipboard.return_value = "paste me"
    ui.read_clipboard_image.return_value = None
    monkeypatch.setattr(clipboard_mod, "MacLLM", Mock(_instance=Mock(ui=ui)))

    result = clipboard_mod.read_clipboard.forward()
    assert result == "paste me"
    assert len(conv.sources) == 1
    assert conv.sources[0]["kind"] == "clipboard"
    assert conv.sources[0]["ref"] == "clipboard"


def test_read_clipboard_image(monkeypatch):
    from macllm.tools import clipboard as clipboard_mod

    conv = Conversation()
    set_current_conversation(conv)
    img = Image.new("RGB", (3, 3), color="blue")

    ui = Mock()
    ui.read_clipboard.return_value = None
    ui.read_clipboard_image.return_value = img
    monkeypatch.setattr(clipboard_mod, "MacLLM", Mock(_instance=Mock(ui=ui)))

    result = clipboard_mod.read_clipboard.forward()
    assert result == "Image observation."
    assert conv.take_observation_images() == [img]
    assert conv.sources[0]["kind"] == "clipboard"


def test_read_file_text(tmp_path):
    from macllm.tools import file as file_mod

    note = tmp_path / "hello.txt"
    note.write_text("hello file")
    FileTag._indexed_directories = [str(tmp_path)]
    FileTag._mount_points = {"Tmp": str(tmp_path)}

    conv = Conversation()
    set_current_conversation(conv)

    result = file_mod.read_file.forward(str(note))
    assert result == "hello file"
    assert conv.sources[0]["kind"] == "file"
    assert conv.sources[0]["ref"].endswith("hello.txt")


def test_read_file_image(tmp_path):
    from macllm.tools import file as file_mod

    img_path = tmp_path / "pic.png"
    Image.new("RGB", (4, 4), color="red").save(str(img_path))
    FileTag._indexed_directories = [str(tmp_path)]
    FileTag._mount_points = {"Tmp": str(tmp_path)}

    conv = Conversation()
    set_current_conversation(conv)

    result = file_mod.read_file.forward(str(img_path))
    assert result == "Image observation."
    images = conv.take_observation_images()
    assert len(images) == 1
    assert conv.sources[0]["kind"] == "file"


def test_macllm_tool_queues_pil_images():
    from macllm.tools._debug import macllm_tool

    conv = Conversation()
    set_current_conversation(conv)
    img = Image.new("RGB", (1, 1))

    @macllm_tool
    def _fake_image_tool() -> str:
        """Return a fake image observation for tests."""
        return img

    out = _fake_image_tool.forward()
    assert out == "Image observation."
    assert conv.take_observation_images() == [img]
