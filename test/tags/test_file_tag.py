import os
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from macllm.core.user_request import UserRequest
from macllm.tags.file_tag import FileTag


class DummyApp:
    """Minimal stub that satisfies FileTag's expectations."""

    debug = False

    def debug_log(self, *args, **kwargs):
        pass

    def debug_exception(self, *args, **kwargs):
        pass


@pytest.fixture

def filetag():
    return FileTag(DummyApp())


@pytest.mark.parametrize(
    "fragment,expected_dir,expected_prefix",
    [
        ("@~/", "~/", ""),
        ("@~/dev/proj", "~/dev/", "proj"),
        ("@/usr/loc", "/usr/", "loc"),
    ],
)
def test_parse_path_fragment(filetag, fragment, expected_dir, expected_prefix):
    dir_raw, prefix = filetag._parse_path_fragment(fragment)
    assert dir_raw == expected_dir
    assert prefix == expected_prefix


def test_autocomplete_live_files_and_dirs(tmp_path):
    base = tmp_path / "dev"
    base.mkdir()

    # File and directory to match the prefix "pro"
    (base / "project1.txt").write_text("x")
    (base / "project2").mkdir()
    (base / "other_file.txt").write_text("y")

    fragment = f'@"{base}/pro'
    tag = FileTag(DummyApp())
    suggestions = tag.autocomplete(fragment, max_results=10)

    # Expect both file and directory suggestions
    assert any("project1.txt" in s for s in suggestions)
    assert any("project2/" in s for s in suggestions)


def test_max_results_enforced(tmp_path):
    for i in range(20):
        (tmp_path / f"file{i}.txt").write_text("")
    fragment = f'@"{tmp_path}/f'
    tag = FileTag(DummyApp())
    results = tag.autocomplete(fragment, max_results=5)
    assert len(results) <= 5


def test_permission_error_handled(tmp_path):
    base = tmp_path / "dir"
    base.mkdir()
    tag = FileTag(DummyApp())
    with patch("os.scandir", side_effect=PermissionError):
        res = tag.autocomplete(f'@"{base}/x')
    assert res == []


def test_min_chars_not_enforced_for_paths(tmp_path):
    # '@/': only one char after '@' but should still return suggestions
    (tmp_path / "foo.txt").write_text("")
    frag = f'@"{tmp_path}/'
    tag = FileTag(DummyApp())
    sug = tag.autocomplete(frag, max_results=10)
    assert sug, "Expected suggestions even with < MIN_CHARS when path-like fragment"


def test_display_string_for_directory(tmp_path):
    base = tmp_path / "mydir"
    base.mkdir()
    tag = FileTag(DummyApp())
    suggestion = f'@"{base}/"'
    display = tag.display_string(suggestion)
    assert display.startswith("📁")
    assert "mydir" in display


# ------------------------------------------------------------------
# Image file tests
# ------------------------------------------------------------------

def _make_conversation_stub():
    conv = Mock()
    conv.context_history = []
    conv.add_context = Mock(return_value="img-ctx")
    return conv


def test_expand_image_file(tmp_path):
    img_path = tmp_path / "photo.png"
    Image.new("RGB", (4, 4), color="blue").save(str(img_path))

    tag = FileTag(DummyApp())
    conv = _make_conversation_stub()
    request = UserRequest("test")

    result = tag.expand(f"@{img_path}", conv, request)

    assert len(request.images) == 1
    assert isinstance(request.images[0], Image.Image)
    assert "[Attached image: photo.png]" in result
    conv.add_context.assert_called_once()
    assert conv.add_context.call_args[1].get("icon") == "🖼️"


def test_expand_image_file_jpeg(tmp_path):
    img_path = tmp_path / "pic.jpg"
    Image.new("RGB", (4, 4), color="red").save(str(img_path))

    tag = FileTag(DummyApp())
    conv = _make_conversation_stub()
    request = UserRequest("test")

    result = tag.expand(f"@{img_path}", conv, request)

    assert len(request.images) == 1
    assert "[Attached image: pic.jpg]" in result


def test_expand_text_file_not_treated_as_image(tmp_path):
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("hello world")

    tag = FileTag(DummyApp())
    conv = _make_conversation_stub()
    request = UserRequest("test")

    result = tag.expand(f"@{txt_path}", conv, request)

    assert len(request.images) == 0
    assert "hello world" in result


# ------------------------------------------------------------------
# External (real LLM) image test
# ------------------------------------------------------------------

@pytest.mark.external
def test_file_image_real(app_real, tmp_path):
    """Send a solid-red image to the real LLM and verify it identifies the color."""
    import time

    img_path = tmp_path / "red_square.png"
    Image.new("RGB", (64, 64), color="red").save(str(img_path))

    app_real.handle_instructions(
        f"What color is this image? Answer with just the color name. @{img_path}"
    )

    max_wait = 20
    waited = 0
    while waited < max_wait:
        if not app_real.is_agent_running() and len(app_real.chat_history.messages) > 0:
            last_msg = app_real.chat_history.messages[-1]
            if last_msg["role"] == "assistant":
                assert "red" in last_msg["content"].lower(), (
                    f"Expected 'red' in response, got: {last_msg['content']}"
                )
                return
        time.sleep(0.5)
        waited += 0.5

    assert False, "Agent did not complete within timeout"
