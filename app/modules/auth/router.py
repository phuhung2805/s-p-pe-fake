from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth import rate_limit, service

router = APIRouter(prefix="/api/auth", tags=["Module 1: Identity & RBAC"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenResponse)
def register_user(req: UserRegister, request: Request, db: Session = Depends(get_db)):
    user, token = service.register_user(db, req, client_ip=_client_ip(request))
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = _client_ip(request)

    # Per-IP sliding-window throttle (defends against distributed brute-force)
    allowed, retry_after = rate_limit.login_ip_limiter.hit(
        client_ip,
        max_events=settings.LOGIN_RATE_LIMIT_MAX,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu đăng nhập. Vui lòng thử lại sau.",
            headers={"Retry-After": str(retry_after)},
        )

    user, token = service.authenticate_user(
        db,
        req.email,
        req.password,
        captcha_token=req.recaptcha_token,
        client_ip=client_ip,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.change_password(db, current_user, req.old_password, req.new_password)
    return MessageResponse(
        message="Đổi mật khẩu thành công. Vui lòng đăng nhập lại bằng mật khẩu mới."
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = _client_ip(request)
    allowed, retry_after = rate_limit.password_reset_ip_limiter.hit(
        client_ip,
        max_events=settings.PASSWORD_RESET_RATE_LIMIT_MAX,
        window_seconds=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu đặt lại mật khẩu. Vui lòng thử lại sau.",
            headers={"Retry-After": str(retry_after)},
        )

    raw_token = service.request_password_reset(db, req.email, client_ip=client_ip)

    # Generic response: never reveal whether the email exists.
    response = ForgotPasswordResponse(
        message="Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi."
    )
    if settings.EXPOSE_RESET_TOKEN and raw_token:
        response.reset_token = raw_token
    return response


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    service.reset_password(db, req.token, req.new_password)
    return MessageResponse(message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_current_user)):
    return user
