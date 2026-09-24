import pytest

from sidge_lunch import fetch


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.content, self.status_code = body, status

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def allow_all(monkeypatch):
    monkeypatch.setattr(fetch, "_robots", lambda origin: type("R", (), {"can_fetch": lambda *a: True})())


@pytest.mark.parametrize("stub, name", [
    (b'<html><head><meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=%2F"></head></html>',
     "SiteGround CAPTCHA"),
    (b"<html><title>You are being redirected...</title><script>var s={},sucuri_cloudproxy_js=''</script></html>",
     "Sucuri JavaScript challenge"),
])
def test_bot_check_pages_are_reported_not_parsed(monkeypatch, stub, name):
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: FakeResponse(stub, 202))
    with pytest.raises(fetch.BotCheck, match=name):
        fetch.fetch("https://example.org/menu")


def test_normal_pages_pass(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: FakeResponse(b"<html><h2>Week Commencing</h2></html>"))
    assert "Week Commencing" in fetch.fetch("https://example.org/menu")
