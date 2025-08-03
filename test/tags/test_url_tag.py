import pytest


@pytest.mark.external
def test_url_tag_real(app_real):
    prompt = (
        "Which of these three companies did guido work for: vmware, intel, google. "
        "Answer only with the two company names, nothing else. "
        "Use @https://guido.appenzeller.net/speaker-biography/"
    )
    response = app_real.handle_instructions(prompt)
    lower = response.lower()
    assert "vmware" in lower
    assert "intel" in lower
    assert "google" not in lower
