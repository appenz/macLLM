import time
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from macllm.core.llm_service import model_supports_vision, _VISION_OVERRIDES, MODELS


class TestModelSupportsVision:
    def test_override_true(self):
        with patch.dict(_VISION_OVERRIDES, {"test/model": True}):
            with patch.dict(MODELS, {"normal": Mock(model_id="test/model")}):
                assert model_supports_vision("normal") is True

    def test_override_false(self):
        with patch.dict(_VISION_OVERRIDES, {"test/model": False}):
            with patch.dict(MODELS, {"normal": Mock(model_id="test/model")}):
                assert model_supports_vision("normal") is False

    def test_falls_back_to_litellm(self):
        with patch.dict(_VISION_OVERRIDES, {}, clear=True):
            with patch.dict(MODELS, {"normal": Mock(model_id="gpt-4o")}):
                with patch("macllm.core.llm_service.litellm") as mock_litellm:
                    mock_litellm.supports_vision.return_value = True
                    assert model_supports_vision("normal") is True
                    mock_litellm.supports_vision.assert_called_once_with(model="gpt-4o")

    def test_none_model_returns_false(self):
        with patch.dict(MODELS, {"fast": None}):
            assert model_supports_vision("fast") is False

    def test_litellm_exception_returns_false(self):
        with patch.dict(_VISION_OVERRIDES, {}, clear=True):
            with patch.dict(MODELS, {"normal": Mock(model_id="unknown/model")}):
                with patch("macllm.core.llm_service.litellm") as mock_litellm:
                    mock_litellm.supports_vision.side_effect = Exception("unknown model")
                    assert model_supports_vision("normal") is False


class TestVisionGatingInHandleInstructions:
    """Verify that images are stripped when the model lacks vision support."""

    def test_images_stripped_when_no_vision(self, app_mocked, monkeypatch):
        app_mocked.ui.read_clipboard_image = lambda: Image.new("RGB", (4, 4))
        app_mocked.ui.read_clipboard = lambda: None

        captured_kwargs = []

        class MockAgent:
            def __init__(self):
                self.memory = Mock(steps=[])

            def run(self, prompt, **kwargs):
                captured_kwargs.append(kwargs)
                return "ok"

        from macllm.core import agent_service
        monkeypatch.setattr(agent_service, "create_agent", lambda **kw: MockAgent())
        monkeypatch.setattr(
            "macllm.core.llm_service.model_supports_vision", lambda speed: False
        )

        app_mocked.chat_history.submit("Describe @clipboard")
        time.sleep(0.2)

        assert len(captured_kwargs) > 0
        assert "images" not in captured_kwargs[0]

    def test_images_passed_when_vision_supported(self, app_mocked, monkeypatch):
        test_image = Image.new("RGB", (4, 4))
        app_mocked.ui.read_clipboard_image = lambda: test_image
        app_mocked.ui.read_clipboard = lambda: None

        captured_kwargs = []

        class MockAgent:
            def __init__(self):
                self.memory = Mock(steps=[])

            def run(self, prompt, **kwargs):
                captured_kwargs.append(kwargs)
                return "ok"

        from macllm.core import agent_service
        monkeypatch.setattr(agent_service, "create_agent", lambda **kw: MockAgent())
        monkeypatch.setattr(
            "macllm.core.llm_service.model_supports_vision", lambda speed: True
        )

        app_mocked.chat_history.submit("Describe @clipboard")
        time.sleep(0.2)

        assert len(captured_kwargs) > 0
        assert "images" in captured_kwargs[0]
        assert captured_kwargs[0]["images"][0] is test_image
