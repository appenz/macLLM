from macllm.tools.shell import _get_conversation, _find_ungranted_paths


class DummyConversation:
    pass


class DummyHistory:
    def __init__(self, conversation):
        self._conversation = conversation

    def get_current_conversation(self):
        return self._conversation


class DummyApp:
    def __init__(self, *, chat_history=None, conversation_history=None):
        self.chat_history = chat_history
        self.conversation_history = conversation_history


def test_get_conversation_uses_chat_history():
    from macllm.macllm import MacLLM

    conversation = DummyConversation()
    MacLLM._instance = DummyApp(chat_history=conversation)
    try:
        assert _get_conversation() is conversation
    finally:
        MacLLM._instance = None


def test_get_conversation_falls_back_to_conversation_history():
    from macllm.macllm import MacLLM

    conversation = DummyConversation()
    history = DummyHistory(conversation)
    MacLLM._instance = DummyApp(chat_history=None, conversation_history=history)
    try:
        assert _get_conversation() is conversation
    finally:
        MacLLM._instance = None


class TestFindUngrantedPaths:
    def test_system_paths_are_allowed(self):
        assert _find_ungranted_paths(["/usr/bin/ls", "/tmp/foo"], []) == []

    def test_granted_path_is_allowed(self):
        granted = ["/Users/me/projects"]
        assert _find_ungranted_paths(["/Users/me/projects/file.txt"], granted) == []

    def test_ungranted_path_flagged(self):
        result = _find_ungranted_paths(["/Users/me/secret"], ["/Users/me/projects"])
        assert result == ["/Users/me/secret"]

    def test_home_dir_flagged(self):
        import os
        home = os.path.expanduser("~")
        result = _find_ungranted_paths([home], [])
        assert result == [home]

    def test_granted_subdir(self):
        granted = ["/Users/me"]
        assert _find_ungranted_paths(["/Users/me/docs/file.txt"], granted) == []
