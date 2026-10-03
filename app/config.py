import os

class Settings:
    PROJECT_NAME: str = "Secure Multi-Vendor E-Commerce with Anti-Tamper QR & Escrow Verification"
    PROJECT_VERSION: str = "1.0.0"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-anti-tamper-key-2026-secure-escrow")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ecommerce_escrow.db")
    DEFAULT_COMMISSION_RATE: float = 0.05  # 5% sàn giao dịch
    DEFAULT_SHIPPING_BASE_FEE: float = 15000.0  # 15,000 VND
    SHIPPING_PER_KM: float = 2000.0  # 2,000 VND / km

settings = Settings()
