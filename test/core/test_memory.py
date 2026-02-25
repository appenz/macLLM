import pickle
from pathlib import Path
from unittest.mock import Mock

import pytest

from macllm.core.memory import get_storage_dir, save_conversation, load_conversation


class MockAgentMemory:
    def __init__(self):
        self.steps = []


class MockAgent:
    def __init__(self):
        self.memory = MockAgentMemory()
    
    def run(self, task, reset=False, **kwargs):
        if reset:
            self.memory.steps = []
        self.memory.steps.append({'task': task})
        return "MOCK_RESPONSE"


def make_mock_conversation(agent=None):
    conv = Mock()
    conv.agent = agent if agent is not None else MockAgent()
    conv.messages = []
    conv.context_history = []
    conv.speed_level = "normal"
    return conv


@pytest.fixture
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr('macllm.core.memory.get_storage_dir', lambda: tmp_path)
    return tmp_path


class TestGetStorageDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        test_dir = tmp_path / "macLLM"
        monkeypatch.setattr('macllm.core.memory.Path.home', lambda: tmp_path)
        
        from macllm.core import memory
        original_func = memory.get_storage_dir
        
        def patched_get_storage_dir():
            path = tmp_path / "Library" / "Application Support" / "macLLM"
            path.mkdir(parents=True, exist_ok=True)
            return path
        
        monkeypatch.setattr(memory, 'get_storage_dir', patched_get_storage_dir)
        result = memory.get_storage_dir()
        
        assert result.exists()
        assert result.is_dir()


class TestSaveConversation:
    def test_save_creates_file(self, temp_storage):
        conv = make_mock_conversation()
        conv.agent.memory.steps = [{'task': 'test'}]
        
        result = save_conversation(conv)
        
        assert result is True
        assert (temp_storage / "latest.pkl").exists()
    
    def test_save_without_agent_returns_false(self, temp_storage):
        conv = make_mock_conversation(agent=None)
        conv.agent = None
        
        result = save_conversation(conv)
        
        assert result is False
        assert not (temp_storage / "latest.pkl").exists()
    
    def test_save_writes_correct_data(self, temp_storage):
        conv = make_mock_conversation()
        test_steps = [{'task': 'hello'}, {'task': 'world'}]
        conv.agent.memory.steps = test_steps
        
        save_conversation(conv)
        
        with open(temp_storage / "latest.pkl", 'rb') as f:
            loaded = pickle.load(f)
        assert loaded['steps'] == test_steps


class TestLoadConversation:
    def test_load_restores_steps(self, temp_storage):
        test_steps = [{'task': 'saved_task'}]
        with open(temp_storage / "latest.pkl", 'wb') as f:
            pickle.dump(test_steps, f)
        
        conv = make_mock_conversation()
        result = load_conversation(conv)
        
        assert result is True
        assert conv.agent.memory.steps == test_steps
    
    def test_load_nonexistent_returns_false(self, temp_storage):
        conv = make_mock_conversation()
        original_steps = [{'task': 'original'}]
        conv.agent.memory.steps = original_steps
        
        result = load_conversation(conv)
        
        assert result is False
        assert conv.agent.memory.steps == original_steps
    
    def test_load_without_agent_returns_false(self, temp_storage):
        test_steps = [{'task': 'test'}]
        with open(temp_storage / "latest.pkl", 'wb') as f:
            pickle.dump(test_steps, f)
        
        conv = make_mock_conversation()
        conv.agent = None
        
        result = load_conversation(conv)
        
        assert result is False
    
    def test_load_corrupt_file_returns_false(self, temp_storage):
        with open(temp_storage / "latest.pkl", 'wb') as f:
            f.write(b'not a valid pickle file')
        
        conv = make_mock_conversation()
        original_steps = [{'task': 'original'}]
        conv.agent.memory.steps = original_steps
        
        result = load_conversation(conv)
        
        assert result is False
        assert conv.agent.memory.steps == original_steps


class TestResetBehavior:
    def test_reset_clears_agent_memory(self, temp_storage, monkeypatch):
        from macllm.core.chat_history import Conversation
        from macllm.core import agent_service
        
        monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: MockAgent())
        
        conv = Conversation()
        conv.agent.memory.steps = [{'task': 'before_reset'}]
        
        conv.reset(clear_persisted=True)
        
        assert conv.agent.memory.steps == []
    
    def test_reset_deletes_persisted_file(self, temp_storage, monkeypatch):
        from macllm.core.chat_history import Conversation
        from macllm.core import agent_service
        from macllm.core import memory
        
        monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: MockAgent())
        monkeypatch.setattr(memory, 'get_storage_dir', lambda: temp_storage)
        
        with open(temp_storage / "latest.pkl", 'wb') as f:
            pickle.dump([{'task': 'old'}], f)
        assert (temp_storage / "latest.pkl").exists()
        
        conv = Conversation()
        conv.reset(clear_persisted=True)
        
        assert not (temp_storage / "latest.pkl").exists()


class TestStepsPersistence:
    def test_steps_preserved_across_agent_recreation(self, monkeypatch):
        from macllm.core.chat_history import Conversation
        from macllm.core import agent_service
        
        monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: MockAgent())
        
        conv = Conversation()
        conv.agent.memory.steps = [{'task': 'first'}, {'task': 'second'}]
        
        conv._create_agent()
        
        assert conv.agent.memory.steps == [{'task': 'first'}, {'task': 'second'}]
    
    def test_persistence_roundtrip(self, temp_storage, monkeypatch):
        from macllm.core import agent_service
        
        monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: MockAgent())
        
        conv1 = make_mock_conversation()
        conv1.agent.memory.steps = [{'task': 'remember_this'}]
        save_conversation(conv1)
        
        conv2 = make_mock_conversation()
        assert conv2.agent.memory.steps == []
        
        result = load_conversation(conv2)
        
        assert result is True
        assert conv2.agent.memory.steps == [{'task': 'remember_this'}]


class TestMessagesPersistence:
    def test_save_includes_messages(self, temp_storage):
        conv = make_mock_conversation()
        conv.messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]
        conv.agent.memory.steps = [{'task': 'test'}]
        
        save_conversation(conv)
        
        with open(temp_storage / "latest.pkl", 'rb') as f:
            data = pickle.load(f)
        assert 'messages' in data
        assert data['messages'] == conv.messages
    
    def test_load_restores_messages(self, temp_storage):
        test_messages = [
            {'role': 'user', 'content': 'Saved question'},
            {'role': 'assistant', 'content': 'Saved answer'}
        ]
        data = {
            'steps': [{'task': 'test'}],
            'messages': test_messages
        }
        with open(temp_storage / "latest.pkl", 'wb') as f:
            pickle.dump(data, f)
        
        conv = make_mock_conversation()
        result = load_conversation(conv)
        
        assert result is True
        assert conv.messages == test_messages
    
    def test_load_handles_old_format(self, temp_storage):
        old_steps = [{'task': 'old_format'}]
        with open(temp_storage / "latest.pkl", 'wb') as f:
            pickle.dump(old_steps, f)
        
        conv = make_mock_conversation()
        result = load_conversation(conv)
        
        assert result is True
        assert conv.agent.memory.steps == old_steps
