import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from the project-root ".env" file regardless of the current
# working directory. With override=False, real environment variables (CI,
# Docker, pytest) always win over the file - so the same code works for local
# dev and automated tests.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    PROJECT_NAME: str = "Secure Multi-Vendor E-Commerce with Anti-Tamper QR & Escrow Verification"
    PROJECT_VERSION: str = "1.1.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-anti-tamper-key-2026-secure-escrow")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))  # 24h
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ecommerce_escrow.db")

    DEFAULT_COMMISSION_RATE: float = 0.05  # 5% sàn giao dịch
    DEFAULT_SHIPPING_BASE_FEE: float = 15000.0  # 15,000 VND
    SHIPPING_PER_KM: float = 2000.0  # 2,000 VND / km

    # ----------------- Public site configuration (exposed via /api/config) -----
    SITE_NAME: str = os.getenv("SITE_NAME", "Escrow Anti-Tamper E-Commerce")
    DEFAULT_LATITUDE: float = float(os.getenv("DEFAULT_LATITUDE", "21.0285"))
    DEFAULT_LONGITUDE: float = float(os.getenv("DEFAULT_LONGITUDE", "105.8542"))

    # ----------------- Bootstrap / seed ---------------------------------------
    # Admin account is seeded from the environment (never hardcoded).
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@ecommerce.vn")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    # Demo data (sample shops/products/orders + demo accounts) is opt-in.
    SEED_DEMO_DATA: bool = _get_bool("SEED_DEMO_DATA", True)

    # ----------------- Module 1: Identity & Security hardening -----------------
    # Public self-registration as Admin is disabled by default to prevent
    # privilege escalation. Seed/bootstrap the admin account out-of-band.
    ALLOW_ADMIN_SELF_REGISTER: bool = _get_bool("ALLOW_ADMIN_SELF_REGISTER", False)

    # Password reset tokens
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
    # In local/dev environments returning the token lets you test the flow
    # without an email provider. NEVER enable this in production.
    EXPOSE_RESET_TOKEN: bool = _get_bool("EXPOSE_RESET_TOKEN", True)

    # Brute-force protection (per account, consecutive failures)
    ACCOUNT_MAX_FAILED_ATTEMPTS: int = int(os.getenv("ACCOUNT_MAX_FAILED_ATTEMPTS", "5"))
    ACCOUNT_LOCKOUT_MINUTES: int = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "15"))

    # Brute-force protection (per client IP, sliding window on login endpoint)
    LOGIN_RATE_LIMIT_MAX: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX", "20"))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))

    # Per client IP sliding window for password-reset requests (anti email bombing)
    PASSWORD_RESET_RATE_LIMIT_MAX: int = int(os.getenv("PASSWORD_RESET_RATE_LIMIT_MAX", "5"))
    PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", "900")
    )

    # Uniform auth errors (ASVS 6.3.8 - Level 3). When true, a locked account
    # returns the exact same generic response as invalid credentials, so valid
    # users cannot be deduced from status code / message.
    AUTH_UNIFORM_ERRORS: bool = _get_bool("AUTH_UNIFORM_ERRORS", True)

    # Breached / weak password screening (ASVS 6.2.4 L1 & 6.2.12 L2)
    BREACH_CHECK_ENABLED: bool = _get_bool("BREACH_CHECK_ENABLED", True)
    # HaveIBeenPwned Pwned Passwords k-anonymity API (free, no key).
    HIBP_ENABLED: bool = _get_bool("HIBP_ENABLED", False)
    HIBP_API_URL: str = os.getenv("HIBP_API_URL", "https://api.pwnedpasswords.com/range/")
    HIBP_TIMEOUT_SECONDS: float = float(os.getenv("HIBP_TIMEOUT_SECONDS", "4"))

    # Security notification emails, e.g. after a password change/reset (ASVS 6.3.7)
    EMAIL_ENABLED: bool = _get_bool("EMAIL_ENABLED", False)
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@ecommerce.vn")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _get_bool("SMTP_USE_TLS", True)

    # ----------------- Captcha (free / invisible) -----------------------------
    # Disabled by default so the app keeps working without keys. Turn it on with
    # CAPTCHA_ENABLED=true and a free key:
    #   * Google reCAPTCHA v3 (invisible, automatic scoring): provider="google"
    #     https://www.google.com/recaptcha/admin  (free tier)
    #   * Cloudflare Turnstile (free, privacy friendly): provider="turnstile"
    #     https://dash.cloudflare.com/?to=/:account/turnstile
    CAPTCHA_ENABLED: bool = _get_bool("CAPTCHA_ENABLED", False)
    CAPTCHA_PROVIDER: str = os.getenv("CAPTCHA_PROVIDER", "google").lower()
    CAPTCHA_SITE_KEY: str = os.getenv("CAPTCHA_SITE_KEY", "")
    CAPTCHA_SECRET_KEY: str = os.getenv("CAPTCHA_SECRET_KEY", "")
    CAPTCHA_MIN_SCORE: float = float(os.getenv("CAPTCHA_MIN_SCORE", "0.5"))
    CAPTCHA_VERIFY_URL: str = os.getenv("CAPTCHA_VERIFY_URL", "")
    # Mock provider only: token that is accepted without any network call.
    CAPTCHA_MOCK_TOKEN: str = os.getenv("CAPTCHA_MOCK_TOKEN", "test-captcha-token")


settings = Settings()
