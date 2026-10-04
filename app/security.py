import hmac
import hashlib
import json
import base64
import time
import secrets
import io
import datetime
import bcrypt
import jwt
import qrcode
from app.config import settings

# ----------------- Password Hashing -----------------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# Constant-time decoy used when an account does not exist, so login timing does
# not leak whether an email is registered.
DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO7ZBp1h1q3fV1oH/0h9Q4zM8Yw1nW8bS"  # bcrypt hash of a random string

def dummy_password_check(password: str) -> None:
    try:
        bcrypt.checkpw(password.encode("utf-8"), DUMMY_PASSWORD_HASH.encode("utf-8"))
    except Exception:
        pass


# ----------------- Password Policy -----------------
def validate_password_strength(password: str) -> None:
    """
    Enforces a minimum password policy. Raises ValueError with a human-readable
    reason when the password is not strong enough.
    """
    if not password or len(password) < 8:
        raise ValueError("Mật khẩu phải có tối thiểu 8 ký tự.")
    if not any(c.isupper() for c in password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ hoa.")
    if not any(c.islower() for c in password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ thường.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ số.")
    if not any(not c.isalnum() for c in password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt.")


# ----------------- Password Reset Tokens -----------------
def generate_reset_token() -> str:
    """Returns a URL-safe, high-entropy password reset token (raw value)."""
    return secrets.token_urlsafe(32)

def hash_reset_token(raw_token: str) -> str:
    """Reset tokens are stored hashed so a DB leak cannot be replayed."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

# ----------------- JWT Authentication -----------------
def create_access_token(data: dict, expires_delta: datetime.timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.datetime.utcnow()})
    # Explicit token typing prevents cross-token confusion (RFC 8725 / OWASP JWT).
    to_encode.setdefault("token_type", "access")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# ----------------- Anti-Tamper HMAC Tokenization -----------------
def generate_package_token(order_id: int, shop_id: int, shop_secret: str):
    """
    Generates an HMAC-SHA256 anti-tamper token:
    Signature = HMAC-SHA256(shop_secret, f"{order_id}:{shop_id}:{timestamp}:{salt}")
    Returns: (token_string, salt, signature, qr_base64_image)
    """
    salt = secrets.token_hex(16)
    timestamp = int(time.time())
    
    # Message to sign
    message = f"ORDER:{order_id}|SHOP:{shop_id}|TS:{timestamp}|SALT:{salt}"
    signature = hmac.new(
        shop_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    payload = {
        "order_id": order_id,
        "shop_id": shop_id,
        "ts": timestamp,
        "salt": salt,
        "sig": signature
    }
    
    # URL-safe compact representation for QR code
    raw_json = json.dumps(payload, separators=(',', ':'))
    token_string = base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")
    
    # Generate QR Code image in base64
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(token_string)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    return token_string, salt, signature, qr_base64

def verify_package_token(token_string: str, shop_secret: str) -> dict:
    """
    Parses and cryptographically verifies the anti-tamper QR token.
    Returns: {"valid": bool, "data": dict, "error": str}
    """
    try:
        raw_json = base64.urlsafe_b64decode(token_string.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)
        
        order_id = payload.get("order_id")
        shop_id = payload.get("shop_id")
        timestamp = payload.get("ts")
        salt = payload.get("salt")
        signature = payload.get("sig")
        
        if not all([order_id, shop_id, timestamp, salt, signature]):
            return {"valid": False, "data": None, "error": "Missing token fields"}
            
        expected_message = f"ORDER:{order_id}|SHOP:{shop_id}|TS:{timestamp}|SALT:{salt}"
        expected_sig = hmac.new(
            shop_secret.encode("utf-8"),
            expected_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, signature):
            return {"valid": False, "data": payload, "error": "Invalid cryptographic signature (Tampered Token)"}
            
        return {"valid": True, "data": payload, "error": None}
    except Exception as e:
        return {"valid": False, "data": None, "error": f"Token decoding error: {str(e)}"}
