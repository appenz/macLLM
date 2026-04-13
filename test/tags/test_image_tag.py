from unittest.mock import Mock, patch

import pytest
from PIL import Image

from macllm.core.user_request import UserRequest
from macllm.tags.image_tag import ImageTag


class DummyApp:
    debug = False

    def debug_log(self, *args, **kwargs):
        pass

    def debug_exception(self, *args, **kwargs):
        pass


def test_expand_populates_request_images(tmp_path):
    img_path = tmp_path / "macllm.png"
    Image.new("RGB", (4, 4), color="green").save(str(img_path))

    tag = ImageTag(DummyApp())
    tag.tmp_image = str(img_path)

    conv = Mock()
    conv.context_history = []
    conv.add_context = Mock(return_value="screenshot-ctx")
    request = UserRequest("test")

    with patch.object(tag, "_capture_screen"):
        result = tag.expand("@selection", conv, request)

    assert len(request.images) == 1
    assert isinstance(request.images[0], Image.Image)
    assert result == "the image"
    conv.add_context.assert_called_once()


def test_expand_window_populates_request_images(tmp_path):
    img_path = tmp_path / "macllm.png"
    Image.new("RGB", (4, 4), color="red").save(str(img_path))

    tag = ImageTag(DummyApp())
    tag.tmp_image = str(img_path)

    conv = Mock()
    conv.context_history = []
    conv.add_context = Mock(return_value="screenshot-ctx")
    request = UserRequest("test")

    with patch.object(tag, "_capture_window"):
        result = tag.expand("@window", conv, request)

    assert len(request.images) == 1
    assert result == "the image"


def test_expand_missing_file_returns_tag():
    tag = ImageTag(DummyApp())
    tag.tmp_image = "/nonexistent/path.png"

    conv = Mock()
    request = UserRequest("test")

    with patch.object(tag, "_capture_screen"):
        result = tag.expand("@selection", conv, request)

    assert result == "@selection"
    assert len(request.images) == 0
