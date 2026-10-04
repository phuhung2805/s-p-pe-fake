"""
Module 1 - Security notification emails (ASVS 6.3.7).

With EMAIL_ENABLED=false (default in dev/test) messages are captured in an
in-memory OUTBOX so we can assert the account owner is notified.
"""
from app.modules.auth import notifications


def test_change_password_sends_notification(client, make_user, headers_for):
    make_user("notif@test.vn", password="Password123!")
    headers = headers_for("notif@test.vn")
    notifications.reset_outbox()

    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "Password123!", "new_password": "NewSecret@2026"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    assert len(notifications.OUTBOX) == 1
    message = notifications.OUTBOX[0]
    assert message["to"] == "notif@test.vn"
    assert "thay đổi" in message["subject"].lower()


def test_forgot_and_reset_send_notifications(client, make_user):
    make_user("notif2@test.vn", password="Password123!")
    notifications.reset_outbox()

    forgot = client.post("/api/auth/forgot-password", json={"email": "notif2@test.vn"})
    token = forgot.json()["reset_token"]

    # The reset token is delivered out-of-band (email side-channel).
    assert any("đặt lại mật khẩu" in m["subject"].lower() for m in notifications.OUTBOX)
    assert any(token in m["body"] for m in notifications.OUTBOX)

    notifications.reset_outbox()
    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewSecret@2026"})
    assert reset.status_code == 200, reset.text
    assert any("đặt lại" in m["subject"].lower() for m in notifications.OUTBOX)


def test_no_notification_for_unknown_email_reset(client):
    notifications.reset_outbox()
    client.post("/api/auth/forgot-password", json={"email": "ghost-notif@test.vn"})
    assert notifications.OUTBOX == []
