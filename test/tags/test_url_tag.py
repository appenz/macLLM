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


def test_url_tag_registers_web_ref():
    tag = URLTag(DummyApp())
    conversation = Conversation()

    result = tag.expand("@https://example.com/some/long/path?a=1", conversation, None)

    assert "web://example.com/1" in result
    assert 'web_fetch("web://example.com/1")' in result
    assert "some/long/path" not in result
    assert conversation.web_pages["web://example.com/1"]["url"] == "https://example.com/some/long/path?a=1"
    assert conversation.context_history[0]["context"] == (
        "Web page reference: web://example.com/1\n"
        'Use web_fetch("web://example.com/1") to retrieve the page text if needed.'
    )


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
