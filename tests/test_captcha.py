"""
Module 1 - Captcha integration tests (free / invisible providers).
"""
from app.config import settings
from app.modules.auth import captcha


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_captcha_disabled_is_a_noop(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", False)
    assert captcha.verify_captcha(None) is True


def test_mock_provider_requires_matching_token(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "mock")
    assert captcha.verify_captcha(None) is False
    assert captcha.verify_captcha("wrong-token") is False
    assert captcha.verify_captcha(settings.CAPTCHA_MOCK_TOKEN) is True


def test_google_provider_score_threshold(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "google")
    monkeypatch.setattr(settings, "CAPTCHA_MIN_SCORE", 0.5)

    monkeypatch.setattr(captcha.httpx, "post", lambda *a, **k: _FakeResponse({"success": True, "score": 0.9}))
    assert captcha.verify_captcha("tok") is True

    monkeypatch.setattr(captcha.httpx, "post", lambda *a, **k: _FakeResponse({"success": True, "score": 0.1}))
    assert captcha.verify_captcha("tok") is False

    monkeypatch.setattr(captcha.httpx, "post", lambda *a, **k: _FakeResponse({"success": False}))
    assert captcha.verify_captcha("tok") is False


def test_google_provider_fails_closed_on_network_error(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "google")

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(captcha.httpx, "post", _boom)
    assert captcha.verify_captcha("tok") is False


def test_login_requires_captcha_when_enabled(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "mock")
    make_user("captcha@test.vn", password="Password123!")

    missing = client.post("/api/auth/login", json={"email": "captcha@test.vn", "password": "Password123!"})
    assert missing.status_code == 400

    ok = client.post(
        "/api/auth/login",
        json={
            "email": "captcha@test.vn",
            "password": "Password123!",
            "recaptcha_token": settings.CAPTCHA_MOCK_TOKEN,
        },
    )
    assert ok.status_code == 200, ok.text


def test_register_requires_captcha_when_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "mock")

    payload = {"email": "capreg@test.vn", "password": "NewSecret@2026", "full_name": "Cap", "role": "Buyer"}
    assert client.post("/api/auth/register", json=payload).status_code == 400

    payload["recaptcha_token"] = settings.CAPTCHA_MOCK_TOKEN
    assert client.post("/api/auth/register", json=payload).status_code == 200
