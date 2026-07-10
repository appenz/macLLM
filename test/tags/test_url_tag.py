import time
import pytest

from macllm.core.chat_history import Conversation
from macllm.tags.url_tag import URLTag


class DummyApp:
    class _Args:
        debug = False

    args = _Args()

    def debug_log(self, *args, **kwargs):
        pass


def test_url_tag_rewrites_to_web_fetch_instruction():
    tag = URLTag(DummyApp())
    conversation = Conversation()
    url = "https://example.com/some/long/path?a=1"

    result = tag.expand(f"@{url}", conversation, None)

    assert url in result
    assert f'web_fetch("{url}")' in result
    assert conversation.sources == []


@pytest.mark.external
def test_url_tag_real(app_real):
    prompt = (
        "Which of these three companies did guido work for: vmware, intel, google. "
        "Answer only with the two company names, nothing else. "
        "Use @https://guido.appenzeller.net/speaker-biography/"
    )
    app_real.chat_history.submit(prompt)

    max_wait = 15
    waited = 0
    while waited < max_wait:
        from macllm.core.conversation_log import messages_from_log

        messages = [
            m for m in messages_from_log(app_real.chat_history.conversation_log)
            if m["role"] in ("user", "assistant")
        ]
        if not app_real.chat_history.is_agent_running() and len(messages) > 0:
            last_msg = messages[-1]
            if last_msg['role'] == 'assistant':
                lower = last_msg['content'].lower()
                assert "vmware" in lower
                assert "intel" in lower
                assert "google" not in lower
                return
        time.sleep(0.5)
        waited += 0.5

    assert False, "Agent did not complete within timeout"
