"""
Module 1 - Breached / weak password screening (ASVS 6.2.4 L1, 6.2.12 L2).
"""
import hashlib

from app.config import settings
from app.modules.auth import breach_check

STRONG = "NewSecret@2026"


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_register_rejects_common_password(client):
    # "Password123!" meets the complexity policy but is a well-known password.
    res = client.post(
        "/api/auth/register",
        json={"email": "common@test.vn", "password": "Password123!", "full_name": "C", "role": "Buyer"},
    )
    assert res.status_code == 400
    assert "phổ biến" in res.json()["detail"].lower()


def test_register_accepts_strong_password(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "strong@test.vn", "password": STRONG, "full_name": "S", "role": "Buyer"},
    )
    assert res.status_code == 200, res.text


def test_change_password_rejects_common_password(client, make_user, headers_for):
    make_user("cpbreach@test.vn", password="Password123!")
    headers = headers_for("cpbreach@test.vn")
    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "Password123!", "new_password": "Welcome@123"},
        headers=headers,
    )
    assert res.status_code == 400


def test_hibp_detects_pwned_password(monkeypatch):
    password = "Zx9!testunique"
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    suffix = sha1[5:]

    monkeypatch.setattr(settings, "HIBP_ENABLED", True)
    monkeypatch.setattr(settings, "BREACH_CHECK_ENABLED", True)
    monkeypatch.setattr(
        breach_check.httpx,
        "get",
        lambda *a, **k: _FakeResponse(f"0000000000000000000000000000000000:1\n{suffix}:42"),
    )
    assert breach_check.is_pwned(password) is True
    assert breach_check.breached_password_reason(password) is not None


def test_hibp_fails_open_on_network_error(monkeypatch):
    monkeypatch.setattr(settings, "HIBP_ENABLED", True)

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(breach_check.httpx, "get", _boom)
    assert breach_check.is_pwned("anything") is False


def test_breach_check_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "BREACH_CHECK_ENABLED", False)
    assert breach_check.breached_password_reason("Password123!") is None
