from unittest.mock import Mock, patch

import pytest

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


class TestObservationImageVisionGating:
    """Vision gating applies when attaching tool observation images to a step."""

    def test_images_attached_when_vision_supported(self):
        from PIL import Image
        from smolagents import ActionStep
        from smolagents.memory import Timing
        from macllm.core.agent_service import create_step_callback
        from macllm.core.chat_history import Conversation

        conv = Conversation()
        img = Image.new("RGB", (4, 4))
        conv.queue_observation_images([img])
        step = ActionStep(step_number=1, timing=Timing(start_time=0.0))
        step.observations = "Clipboard contains an image."

        with patch("macllm.core.llm_service.model_supports_vision", return_value=True):
            create_step_callback(conv)(step, Mock())

        assert step.observations_images == [img]

    def test_images_omitted_when_no_vision(self):
        from PIL import Image
        from smolagents import ActionStep
        from smolagents.memory import Timing
        from macllm.core.agent_service import create_step_callback
        from macllm.core.chat_history import Conversation

        conv = Conversation()
        img = Image.new("RGB", (4, 4))
        conv.queue_observation_images([img])
        step = ActionStep(step_number=1, timing=Timing(start_time=0.0))
        step.observations = "Clipboard contains an image."

        with patch("macllm.core.llm_service.model_supports_vision", return_value=False):
            create_step_callback(conv)(step, Mock())

        assert not getattr(step, "observations_images", None)
        assert "does not support vision" in step.observations
