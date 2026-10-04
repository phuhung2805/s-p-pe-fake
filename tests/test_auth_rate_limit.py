"""
Module 1 - Brute-force protection tests: per-account lockout + per-IP throttle.
"""
import datetime

from app.config import settings
from app.models import User


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_account_locks_after_max_failed_attempts(client, make_user, db, monkeypatch):
    # Verbose lockout messaging (opt-out of uniform errors) exposes a 429.
    monkeypatch.setattr(settings, "AUTH_UNIFORM_ERRORS", False)
    make_user("lock@test.vn", password="Password123!")
    max_attempts = settings.ACCOUNT_MAX_FAILED_ATTEMPTS

    responses = [_login(client, "lock@test.vn", "WrongPass@1") for _ in range(max_attempts)]
    assert responses[-1].status_code == 429, responses[-1].text
    assert responses[-1].headers.get("retry-after")

    # Correct password is refused while locked
    assert _login(client, "lock@test.vn", "Password123!").status_code == 429

    user = db.query(User).filter(User.email == "lock@test.vn").first()
    assert user.locked_until is not None
    assert user.failed_login_attempts >= max_attempts


def test_locked_account_is_indistinguishable_by_default(client, make_user, db):
    """ASVS 6.3.8: locked accounts must look identical to wrong credentials."""
    make_user("hidden@test.vn", password="Password123!")
    for _ in range(settings.ACCOUNT_MAX_FAILED_ATTEMPTS):
        _login(client, "hidden@test.vn", "WrongPass@1")

    user = db.query(User).filter(User.email == "hidden@test.vn").first()
    assert user.locked_until is not None

    locked = _login(client, "hidden@test.vn", "Password123!")
    unknown = _login(client, "ghost-account@test.vn", "WrongPass@1")
    assert locked.status_code == 401
    assert unknown.status_code == 401
    assert locked.json()["detail"] == unknown.json()["detail"]


def test_login_succeeds_after_lockout_expires(client, make_user, db):
    user = make_user("expire@test.vn", password="Password123!")
    # Simulate an expired lockout window.
    user.locked_until = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
    user.failed_login_attempts = settings.ACCOUNT_MAX_FAILED_ATTEMPTS
    db.commit()

    res = _login(client, "expire@test.vn", "Password123!")
    assert res.status_code == 200, res.text

    db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_successful_login_resets_failed_counter(client, make_user, db):
    make_user("reset-counter@test.vn", password="Password123!")
    _login(client, "reset-counter@test.vn", "WrongPass@1")
    _login(client, "reset-counter@test.vn", "WrongPass@1")
    assert _login(client, "reset-counter@test.vn", "Password123!").status_code == 200

    user = db.query(User).filter(User.email == "reset-counter@test.vn").first()
    assert user.failed_login_attempts == 0


def test_per_ip_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300)

    for _ in range(3):
        assert _login(client, "nobody@test.vn", "x").status_code == 401

    blocked = _login(client, "nobody@test.vn", "x")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
