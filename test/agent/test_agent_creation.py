import time
from unittest.mock import Mock, patch

from macllm.macllm import create_macllm
from macllm.agents.default import MacLLMDefaultAgent
from macllm.agents.smolagent import MacLLMSmolAgent


class TestAgentSelection:
    def test_default_agent_on_startup(self):
        mac = create_macllm(debug=False, start_ui=False)
        assert mac.chat_history.agent_cls is MacLLMDefaultAgent

    def test_agent_tag_switches_agent_class(self):
        mac = create_macllm(debug=False, start_ui=False)

        with patch('macllm.core.agent_service.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.macllm_name = "smolagent"
            mock_agent.memory = Mock(steps=[])
            mock_create.return_value = mock_agent

            mac.handle_instructions("@agent:smolagent hello")
            time.sleep(0.3)

        assert mac.chat_history.agent_cls is MacLLMSmolAgent

    def test_agent_persists_without_tag(self):
        mac = create_macllm(debug=False, start_ui=False)

        with patch('macllm.core.agent_service.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.macllm_name = "smolagent"
            mock_agent.memory = Mock(steps=[])
            mock_create.return_value = mock_agent

            mac.handle_instructions("@agent:smolagent first message")
            time.sleep(0.3)

        assert mac.chat_history.agent_cls is MacLLMSmolAgent

        with patch('macllm.core.agent_service.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.macllm_name = "smolagent"
            mock_agent.memory = Mock(steps=[])
            mock_create.return_value = mock_agent

            mac.handle_instructions("second message without tag")
            time.sleep(0.3)

        assert mac.chat_history.agent_cls is MacLLMSmolAgent

    def test_new_conversation_resets_to_default(self):
        mac = create_macllm(debug=False, start_ui=False)
        mac.chat_history.agent_cls = MacLLMSmolAgent

        new_conv = mac.conversation_history.add_conversation()
        new_conv.ui_update_callback = mac._update_ui_from_callback
        mac.chat_history = new_conv

        assert mac.chat_history._get_agent_cls() is MacLLMDefaultAgent


class TestUserRequestAgentName:
    def test_default_is_none(self):
        from macllm.core.user_request import UserRequest
        req = UserRequest("hello")
        assert req.agent_name is None


class TestMemoryAgentPersistence:
    def test_save_includes_agent_name(self, tmp_path, monkeypatch):
        import pickle
        from macllm.core.memory import save_conversation

        monkeypatch.setattr('macllm.core.memory.get_storage_dir', lambda: tmp_path)

        conv = Mock()
        conv.agent = Mock()
        conv.agent.memory = Mock(steps=[])
        conv.agent.macllm_name = "smolagent"
        conv.messages = []

        save_conversation(conv)

        with open(tmp_path / "latest.pkl", 'rb') as f:
            data = pickle.load(f)
        assert data['agent_name'] == 'smolagent'

    def test_load_old_format_defaults_to_default(self, tmp_path, monkeypatch):
        import pickle
        from macllm.core.memory import load_conversation

        monkeypatch.setattr('macllm.core.memory.get_storage_dir', lambda: tmp_path)

        data = {'steps': [], 'messages': []}
        with open(tmp_path / "latest.pkl", 'wb') as f:
            pickle.dump(data, f)

        conv = Mock()
        conv.agent = Mock()
        conv.agent.memory = Mock(steps=[])
        conv.agent_cls = None

        load_conversation(conv)

        assert conv.agent_cls is MacLLMDefaultAgent
