"""
Security notification emails (Module 1) - ASVS 6.3.7.

After sensitive credential changes (password change / reset) the account owner
must be notified. This module is pluggable:

* EMAIL_ENABLED=false (default): messages are captured in an in-memory OUTBOX
  and logged, so the flow is observable in dev/tests without an SMTP server.
* EMAIL_ENABLED=true: sends real email via SMTP.
"""
import logging
import smtplib
from email.message import EmailMessage
from typing import Dict, List

from app.config import settings

logger = logging.getLogger(__name__)

# Observable in dev/test when real email delivery is disabled.
OUTBOX: List[Dict[str, str]] = []


def reset_outbox() -> None:
    OUTBOX.clear()


def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.EMAIL_ENABLED:
        OUTBOX.append({"to": to, "subject": subject, "body": body})
        logger.info("[email:dev] to=%s subject=%s", to, subject)
        return True

    try:
        message = EmailMessage()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.warning("Failed to send security email to %s: %s", to, exc)
        return False


def send_password_changed_email(user) -> bool:
    return send_email(
        user.email,
        "Mật khẩu của bạn đã được thay đổi",
        (
            f"Xin chào {user.full_name},\n\n"
            f"Mật khẩu cho tài khoản {user.email} vừa được thay đổi.\n"
            "Nếu không phải bạn thực hiện, hãy liên hệ bộ phận hỗ trợ NGAY và đặt lại mật khẩu.\n"
        ),
    )


def send_password_reset_link_email(user, token: str) -> bool:
    return send_email(
        user.email,
        "Yêu cầu đặt lại mật khẩu",
        (
            f"Xin chào {user.full_name},\n\n"
            "Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu cho tài khoản "
            f"{user.email}.\n"
            f"Dùng token sau để đặt lại mật khẩu: {token}\n"
            f"Token sẽ hết hạn sau {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} phút "
            "và chỉ dùng được một lần.\n"
            "Nếu không phải bạn yêu cầu, hãy bỏ qua email này.\n"
        ),
    )


def send_password_reset_email(user) -> bool:
    return send_email(
        user.email,
        "Mật khẩu của bạn đã được đặt lại",
        (
            f"Xin chào {user.full_name},\n\n"
            f"Mật khẩu cho tài khoản {user.email} vừa được đặt lại thành công.\n"
            "Nếu không phải bạn thực hiện, hãy liên hệ bộ phận hỗ trợ NGAY.\n"
        ),
    )
