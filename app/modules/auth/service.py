"""
Module 1 - Identity, RBAC & Auth security business logic.

Covers: registration hardening, brute-force protected login, password change,
and token-based forgot/reset password.
"""
import datetime
import secrets
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuditLog, PasswordResetToken, Shop, User, UserRole
from app.schemas import UserRegister
from app.security import (
    create_access_token,
    dummy_password_check,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    validate_password_strength,
    verify_password,
)
from app.modules.auth import breach_check, captcha, notifications


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _audit(db: Session, event_type: str, user_id: Optional[int] = None, details: Optional[str] = None) -> None:
    db.add(AuditLog(event_type=event_type, user_id=user_id, details=details))
    db.commit()


def _validate_password(password: str) -> None:
    """Password policy + breached/weak password screening (ASVS 6.2.4/6.2.12)."""
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    reason = breach_check.breached_password_reason(password)
    if reason:
        raise HTTPException(status_code=400, detail=reason)


def _issue_token(user: User) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "email": user.email,
            "ver": user.token_version,
        }
    )


def _assert_captcha(token: Optional[str], client_ip: Optional[str]) -> None:
    if not captcha.verify_captcha(token, client_ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha verification failed. Please try again.",
        )


def register_user(db: Session, req: UserRegister, client_ip: Optional[str] = None) -> Tuple[User, str]:
    _assert_captcha(req.recaptcha_token, client_ip)

    if req.role not in UserRole.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(UserRole.ALL)}")

    if req.role == UserRole.ADMIN and not settings.ALLOW_ADMIN_SELF_REGISTER:
        raise HTTPException(
            status_code=403,
            detail="Admin accounts cannot be self-registered. Contact the platform administrator.",
        )

    _validate_password(req.password)

    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = User(
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        phone=req.phone,
        role=req.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if req.role == UserRole.SHOP:
        shop = Shop(
            owner_id=new_user.id,
            shop_name=f"Shop của {new_user.full_name}",
            address="Hà Nội, Việt Nam",
            latitude=21.0285,
            longitude=105.8542,
            commission_rate=0.05,
            wallet_balance=0.0,
            shop_secret=secrets.token_hex(32),
        )
        db.add(shop)
        db.commit()

    _audit(db, "AUTH_REGISTERED", user_id=new_user.id, details=f"New {new_user.role} registered: {new_user.email}")
    return new_user, _issue_token(new_user)


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    captcha_token: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> Tuple[User, str]:
    _assert_captcha(captcha_token, client_ip)

    email = email.lower()
    user = db.query(User).filter(User.email == email).first()

    # Account lockout check (persistent brute-force protection)
    if user and user.locked_until and user.locked_until > _now():
        retry_after = int((user.locked_until - _now()).total_seconds()) + 1
        _audit(db, "AUTH_LOCKED_OUT", user_id=user.id, details=f"Login attempt on locked account {email}")
        if settings.AUTH_UNIFORM_ERRORS:
            # ASVS 6.3.8: do not reveal that the account exists / is locked.
            raise HTTPException(status_code=401, detail="Invalid email or password")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Tài khoản đang bị tạm khóa do đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.",
            headers={"Retry-After": str(retry_after)},
        )

    # Lockout window elapsed: reset the failure counter so the user gets a fresh try.
    if user and user.locked_until and user.locked_until <= _now():
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    if not user:
        # Constant-time decoy to avoid user enumeration via timing.
        dummy_password_check(password)
        _audit(db, "AUTH_LOGIN_FAILED", details=f"Login failed for unknown email {email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        locked_now = user.failed_login_attempts >= settings.ACCOUNT_MAX_FAILED_ATTEMPTS
        if locked_now:
            user.locked_until = _now() + datetime.timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        db.commit()

        _audit(
            db,
            "AUTH_LOGIN_FAILED",
            user_id=user.id,
            details=f"Failed login #{user.failed_login_attempts} for {email}",
        )

        if locked_now and not settings.AUTH_UNIFORM_ERRORS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Sai mật khẩu quá nhiều lần. Tài khoản đã bị tạm khóa "
                    f"{settings.ACCOUNT_LOCKOUT_MINUTES} phút."
                ),
                headers={"Retry-After": str(settings.ACCOUNT_LOCKOUT_MINUTES * 60)},
            )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Success: clear lock counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _now()
    db.commit()
    db.refresh(user)

    _audit(db, "AUTH_LOGIN_SUCCESS", user_id=user.id, details=f"Login success for {email}")
    return user, _issue_token(user)


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")

    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu mới không được trùng với mật khẩu hiện tại.")

    _validate_password(new_password)

    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    user.token_version = (user.token_version or 0) + 1  # revoke all existing sessions
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    _audit(db, "PASSWORD_CHANGED", user_id=user.id, details=f"Password changed for {user.email}")
    # ASVS 6.3.7: notify the account owner of the credential change.
    notifications.send_password_changed_email(user)


def request_password_reset(db: Session, email: str, client_ip: Optional[str] = None) -> Optional[str]:
    """
    Creates a reset token when the account exists. Always behaves identically
    for unknown emails to avoid account enumeration.
    """
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        _audit(db, "PASSWORD_RESET_REQUESTED", details=f"Reset requested for unknown email {email}")
        return None

    # Invalidate any previously issued, still-unused tokens.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).update({PasswordResetToken.used: True})

    raw_token = generate_reset_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=_now() + datetime.timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        requested_ip=client_ip,
    )
    db.add(reset)
    db.commit()

    _audit(db, "PASSWORD_RESET_REQUESTED", user_id=user.id, details=f"Password reset requested for {email}")
    # Side-channel delivery of the reset token (ASVS 6.4.3).
    notifications.send_password_reset_link_email(user, raw_token)
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    token_hash = hash_reset_token(raw_token)
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if not reset or reset.used:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không hợp lệ hoặc đã được sử dụng.")

    if reset.expires_at < _now():
        reset.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu đã hết hạn.")

    _validate_password(new_password)

    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    user.token_version = (user.token_version or 0) + 1  # revoke all sessions
    user.failed_login_attempts = 0
    user.locked_until = None

    # Single-use: burn this token and any other outstanding one.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).update({PasswordResetToken.used: True})
    db.commit()

    _audit(db, "PASSWORD_RESET_COMPLETED", user_id=user.id, details=f"Password reset completed for {user.email}")
    # ASVS 6.3.7: notify the account owner of the credential reset.
    notifications.send_password_reset_email(user)
