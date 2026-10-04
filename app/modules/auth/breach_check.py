"""
Breached / weak password screening (Module 1).

Implements ASVS 6.2.4 (top common passwords matching the password policy) and
6.2.12 (breached-password check). Two layers:

1. A bundled offline blocklist of the most common/weak passwords (always on).
2. Optional HaveIBeenPwned "Pwned Passwords" k-anonymity range API (free, no
   API key, the password is never sent in full).

The HIBP lookup fails *open* (allows the password) on network errors so a
provider outage cannot block registration - it is a defense-in-depth control.
"""
import hashlib
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Offline blocklist: common passwords / patterns (lower-cased).
COMMON_PASSWORDS = frozenset(
    {
        "123456", "123456789", "password", "12345678", "qwerty", "111111", "123123",
        "12345", "1234567890", "000000", "admin", "letmein", "welcome", "monkey",
        "dragon", "football", "iloveyou", "master", "sunshine", "princess",
        "qwerty123", "password1", "password123", "password123!", "password1234",
        "abc123", "1q2w3e4r", "qwertyuiop", "1234567", "1234", "123456a",
        "1qaz2wsx", "123qwe", "654321", "superman", "batman", "trustno1",
        "passw0rd", "p@ssw0rd", "p@ssword", "qazwsx", "121212", "555555",
        "666666", "777777", "888888", "999999", "123321", "112233", "159753",
        "zxcvbnm", "asdfghjkl", "qwerty1234", "test123", "test1234", "test@123",
        "admin123", "admin@123", "admin1234", "root", "toor", "guest", "user",
        "changeme", "secret", "pass123", "hello123", "whatever", "baseball",
        "shadow", "michael", "jennifer", "jordan", "hunter", "ranger", "buster",
        "soccer", "harley", "andrew", "tigger", "summer", "ginger", "cookie",
        "cheese", "pepper", "matrix", "killer", "joshua", "liverpool", "chelsea",
        "arsenal", "barcelona", "madrid", "computer", "internet", "samsung",
        "google", "facebook", "twitter", "linkedin", "microsoft", "apple123",
        "nokia", "motorola", "blackberry", "huawei", "xiaomi", "abcd1234",
        "a1234567", "qwer1234", "1qazxsw2", "zaq12wsx", "welcome1", "welcome@123",
        "welcome123", "abc@1234", "aa123456", "abcdefg", "00000000", "password!",
        "iloveyou1", "sunshine1", "princess1", "football1", "monkey123",
        "qwerty1", "123456789a", "password12", "zxcvbnm123", "asdf1234",
        "1q2w3e4r5t", "q1w2e3r4", "q1w2e3r4t5", "maiyeuem", "matkhau", "123456789",
    }
)


def is_common_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS


def is_pwned(password: str) -> bool:
    """Checks the password against the HIBP Pwned Passwords range API."""
    if not settings.HIBP_ENABLED:
        return False
    try:
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        url = f"{settings.HIBP_API_URL}{prefix}"
        response = httpx.get(
            url,
            headers={"Add-Padding": "true", "User-Agent": "btl-cnpm-auth/1.0"},
            timeout=settings.HIBP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for line in response.text.splitlines():
            hash_suffix, _, _count = line.partition(":")
            if hash_suffix.strip().upper() == suffix:
                return True
        return False
    except Exception as exc:  # fail open: never block signup on provider outage
        logger.warning("HIBP breached-password check failed, allowing password: %s", exc)
        return False


def breached_password_reason(password: str) -> Optional[str]:
    """Returns a user-facing reason when the password is weak/breached, else None."""
    if not settings.BREACH_CHECK_ENABLED:
        return None
    if is_common_password(password):
        return "Mật khẩu nằm trong danh sách các mật khẩu phổ biến/yếu. Vui lòng chọn mật khẩu khác."
    if is_pwned(password):
        return "Mật khẩu đã xuất hiện trong các vụ rò rỉ dữ liệu. Vui lòng chọn mật khẩu khác."
    return None
