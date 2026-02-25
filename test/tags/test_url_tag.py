import time
import pytest


@pytest.mark.external
def test_url_tag_real(app_real):
    prompt = (
        "Which of these three companies did guido work for: vmware, intel, google. "
        "Answer only with the two company names, nothing else. "
        "Use @https://guido.appenzeller.net/speaker-biography/"
    )
    app_real.handle_instructions(prompt)
    
    max_wait = 15
    waited = 0
    while waited < max_wait:
        if app_real.chat_history.agent_status == "" and len(app_real.chat_history.messages) > 0:
            last_msg = app_real.chat_history.messages[-1]
            if last_msg['role'] == 'assistant' and last_msg['content'] != "How can I help you?":
                response = last_msg['content']
                lower = response.lower()
                assert "vmware" in lower
                assert "intel" in lower
                assert "google" not in lower
                return
        time.sleep(0.5)
        waited += 0.5
    
    assert False, "Agent did not complete within timeout"
