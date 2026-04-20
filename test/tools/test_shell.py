from macllm.tools.shell import _get_conversation, _find_ungranted_paths


class DummyConversation:
    pass


class DummyApp:
    def __init__(self, *, chat_history=None):
        self.chat_history = chat_history


def test_get_conversation_uses_chat_history():
    """get_current_conversation falls back to MacLLM._instance.chat_history on the main thread."""
    from macllm.macllm import MacLLM

    conversation = DummyConversation()
    MacLLM._instance = DummyApp(chat_history=conversation)
    try:
        assert _get_conversation() is conversation
    finally:
        MacLLM._instance = None


def test_get_conversation_uses_thread_local():
    """When a thread-local conversation is set, it takes priority."""
    import threading
    from macllm.core.context import set_current_conversation, _thread_context

    conversation = DummyConversation()
    set_current_conversation(conversation)
    try:
        assert _get_conversation() is conversation
    finally:
        _thread_context.conversation = None


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
