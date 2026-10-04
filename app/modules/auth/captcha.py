"""
Captcha verification for auth endpoints (Module 1 - Auth & Security).

Supports free, low-friction providers:
  * Google reCAPTCHA v3  -> invisible, returns a risk score (automatic)
  * Cloudflare Turnstile -> free, privacy friendly
  * mock                 -> deterministic, for tests / offline demos

The feature is opt-in via ``CAPTCHA_ENABLED``. When disabled the verifier is a
no-op so the application keeps working without any keys.
"""
from typing import Optional

import httpx

from app.config import settings

DEFAULT_VERIFY_URLS = {
    "google": "https://www.google.com/recaptcha/api/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
}


def _verify_url() -> str:
    if settings.CAPTCHA_VERIFY_URL:
        return settings.CAPTCHA_VERIFY_URL
    return DEFAULT_VERIFY_URLS.get(settings.CAPTCHA_PROVIDER, DEFAULT_VERIFY_URLS["google"])


def verify_captcha(token: Optional[str], remote_ip: Optional[str] = None) -> bool:
    """
    Returns True when the captcha challenge is valid (or when captcha is disabled).
    Fails closed on network / provider errors.
    """
    if not settings.CAPTCHA_ENABLED:
        return True

    if not token:
        return False

    if settings.CAPTCHA_PROVIDER == "mock":
        return token == settings.CAPTCHA_MOCK_TOKEN

    payload = {"secret": settings.CAPTCHA_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = httpx.post(_verify_url(), data=payload, timeout=5.0)
        data = response.json()
    except Exception:
        # Fail closed: if we cannot verify, deny the action.
        return False

    if not data.get("success"):
        return False

    # reCAPTCHA v3 returns a score between 0.0 (bot) and 1.0 (human).
    if settings.CAPTCHA_PROVIDER == "google" and "score" in data:
        try:
            if float(data["score"]) < settings.CAPTCHA_MIN_SCORE:
                return False
        except (TypeError, ValueError):
            return False

    return True
