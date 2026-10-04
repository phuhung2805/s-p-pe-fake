"""
Module 1 - JWT hardening tests (OWASP JWT Cheat Sheet / RFC 8725).

Verifies explicit token typing: a token that is not an access token (or is
missing the token_type claim) must be rejected, preventing token-type confusion.
"""
import datetime

import jwt

from app.config import settings


def _encode(payload):
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _base_payload(user, token_type=None):
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "ver": user.token_version,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        "iat": datetime.datetime.utcnow(),
    }
    if token_type is not None:
        payload["token_type"] = token_type
    return payload


def test_valid_access_token_is_accepted(client, make_user):
    user = make_user("jwt-ok@test.vn")
    token = _encode(_base_payload(user, token_type="access"))
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text


def test_token_without_token_type_is_rejected(client, make_user):
    user = make_user("jwt-notype@test.vn")
    token = _encode(_base_payload(user, token_type=None))
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_non_access_token_type_is_rejected(client, make_user):
    user = make_user("jwt-reset@test.vn")
    token = _encode(_base_payload(user, token_type="password_reset"))
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_token_signed_with_wrong_key_is_rejected(client, make_user):
    user = make_user("jwt-badkey@test.vn")
    payload = _base_payload(user, token_type="access")
    forged = jwt.encode(payload, "attacker-key", algorithm="HS256")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401
