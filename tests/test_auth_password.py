"""
Module 1 - Password lifecycle tests: change password + forgot/reset password.
"""
import datetime

from app.models import PasswordResetToken, User
from app.security import hash_reset_token

STRONG = "NewSecret@2026"


def test_register_rejects_admin_self_registration(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "evil-admin@test.vn",
            "password": STRONG,
            "full_name": "Evil",
            "role": "Admin",
        },
    )
    assert res.status_code == 403


def test_register_rejects_weak_password(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "weak@test.vn", "password": "weakpass", "full_name": "Weak", "role": "Buyer"},
    )
    assert res.status_code == 400
    assert "mật khẩu" in res.json()["detail"].lower()


def test_register_and_login_roundtrip(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "newbie@test.vn", "password": STRONG, "full_name": "Newbie", "role": "Buyer"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "Buyer"

    login = client.post("/api/auth/login", json={"email": "newbie@test.vn", "password": STRONG})
    assert login.status_code == 200


def test_change_password_success_and_revokes_old_token(client, make_user, headers_for):
    make_user("cp@test.vn", password="Password123!")
    headers = headers_for("cp@test.vn")

    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "Password123!", "new_password": STRONG},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # Old token is now revoked (token_version bumped)
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    # Old password no longer works, new one does
    assert client.post("/api/auth/login", json={"email": "cp@test.vn", "password": "Password123!"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "cp@test.vn", "password": STRONG}).status_code == 200


def test_change_password_wrong_current(client, make_user, headers_for):
    make_user("cp2@test.vn")
    headers = headers_for("cp2@test.vn")
    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "WrongPass@1", "new_password": STRONG},
        headers=headers,
    )
    assert res.status_code == 400


def test_change_password_rejects_reuse(client, make_user, headers_for):
    make_user("cp3@test.vn", password="Password123!")
    headers = headers_for("cp3@test.vn")
    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "Password123!", "new_password": "Password123!"},
        headers=headers,
    )
    assert res.status_code == 400


def test_change_password_requires_auth(client):
    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "x", "new_password": STRONG},
    )
    assert res.status_code == 401


def test_forgot_and_reset_password_flow(client, make_user):
    make_user("reset@test.vn", password="Password123!")

    forgot = client.post("/api/auth/forgot-password", json={"email": "reset@test.vn"})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    assert token

    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": STRONG})
    assert reset.status_code == 200, reset.text

    # Token is single-use
    reuse = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another@2026"})
    assert reuse.status_code == 400

    assert client.post("/api/auth/login", json={"email": "reset@test.vn", "password": "Password123!"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "reset@test.vn", "password": STRONG}).status_code == 200


def test_forgot_password_unknown_email_is_generic(client):
    res = client.post("/api/auth/forgot-password", json={"email": "ghost@test.vn"})
    assert res.status_code == 200
    body = res.json()
    assert body["reset_token"] is None
    assert "email" in body["message"].lower() or "tồn tại" in body["message"]


def test_reset_password_invalid_token(client):
    res = client.post("/api/auth/reset-password", json={"token": "garbage", "new_password": STRONG})
    assert res.status_code == 400


def test_reset_password_expired_token(client, make_user, db):
    user = make_user("expired@test.vn", password="Password123!")
    raw = "expired-token-value"
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
            used=False,
        )
    )
    db.commit()

    res = client.post("/api/auth/reset-password", json={"token": raw, "new_password": STRONG})
    assert res.status_code == 400
    assert "hết hạn" in res.json()["detail"].lower()


def test_reset_password_rejects_weak_password(client, make_user, db):
    user = make_user("weakreset@test.vn", password="Password123!")
    raw = "weak-reset-token"
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            used=False,
        )
    )
    db.commit()

    res = client.post("/api/auth/reset-password", json={"token": raw, "new_password": "weakpass"})
    assert res.status_code == 400


def test_reset_token_stored_hashed_not_plaintext(client, make_user, db):
    make_user("hashed@test.vn", password="Password123!")
    forgot = client.post("/api/auth/forgot-password", json={"email": "hashed@test.vn"})
    raw = forgot.json()["reset_token"]

    stored = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash_reset_token(raw)).first()
    assert stored is not None
    # The raw token must never be persisted directly.
    assert stored.token_hash != raw

    # Password reset must bump token_version (revoke active sessions).
    user = db.query(User).filter(User.email == "hashed@test.vn").first()
    before = user.token_version
    client.post("/api/auth/reset-password", json={"token": raw, "new_password": STRONG})
    db.refresh(user)
    assert user.token_version == before + 1
