import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole:
    ADMIN = "Admin"
    SHOP = "Shop"
    SHIPPER = "Shipper"
    BUYER = "Buyer"
    ALL = [ADMIN, SHOP, SHIPPER, BUYER]

class OrderStatus:
    PENDING = "PENDING"
    PAID_ESCROW = "PAID_ESCROW"
    PACKED = "PACKED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED_VERIFIED = "DELIVERED_VERIFIED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"

class PackageStatus:
    CREATED = "CREATED"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    TAMPERED = "TAMPERED"

class EscrowStatus:
    HELD = "HELD"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"

class DisputeStatus:
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FRAUD_FLAGGED = "FRAUD_FLAGGED"

class PaymentMethod:
    COD = "COD"
    WALLET_ESCROW = "WALLET_ESCROW"
    VNPAY_ESCROW = "VNPAY_ESCROW"
    MOMO_ESCROW = "MOMO_ESCROW"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), nullable=False, default=UserRole.BUYER)
    fraud_score = Column(Integer, default=0)  # Fraud warning score (Module 8)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Security fields (Module 1)
    token_version = Column(Integer, nullable=False, default=0)  # Bumped to revoke all issued JWTs
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)  # Account lockout after repeated failures
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

    # Relationships
    shops = relationship("Shop", back_populates="owner", cascade="all, delete-orphan")
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    buyer_orders = relationship("Order", back_populates="buyer", foreign_keys="[Order.buyer_id]")
    shipper_packages = relationship("Package", back_populates="shipper", foreign_keys="[Package.shipper_id]")
    disputes = relationship("Dispute", back_populates="reporter")
    reviews = relationship("Review", back_populates="buyer")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shop_name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, default=21.0285)   # Default Hanoi coords
    longitude = Column(Float, default=105.8542)
    commission_rate = Column(Float, default=0.05)  # 5% default
    wallet_balance = Column(Float, default=0.0)
    shop_secret = Column(String(128), nullable=False)  # Secret key for HMAC tokenization

    # Relationships
    owner = relationship("User", back_populates="shops")
    products = relationship("Product", back_populates="shop", cascade="all, delete-orphan")
    packages = relationship("Package", back_populates="shop")
    order_items = relationship("OrderItem", back_populates="shop")
    escrow_wallets = relationship("EscrowWallet", back_populates="shop")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    category = Column(String(100), nullable=False, index=True)
    images = Column(Text, nullable=True)  # Comma-separated or JSON list of URLs

    # Relationships
    shop = relationship("Shop", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=True)  # Sub-order per shop
    total_amount = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    final_amount = Column(Float, nullable=False)
    status = Column(String(50), default=OrderStatus.PENDING, index=True)
    shipping_address = Column(String(255), nullable=False)
    buyer_latitude = Column(Float, default=21.0300)
    buyer_longitude = Column(Float, default=105.8500)
    masked_phone = Column(String(50), nullable=True)
    payment_method = Column(String(50), default=PaymentMethod.WALLET_ESCROW)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    buyer = relationship("User", back_populates="buyer_orders", foreign_keys=[buyer_id])
    shop = relationship("Shop", foreign_keys=[shop_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    packages = relationship("Package", back_populates="order", cascade="all, delete-orphan")
    escrow = relationship("EscrowWallet", back_populates="order", uselist=False, cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="order")
    reviews = relationship("Review", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    status = Column(String(50), default="ACTIVE")

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    shop = relationship("Shop", back_populates="order_items")


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    shipper_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Cryptographic anti-tamper fields
    package_token_hash = Column(String(255), nullable=False, index=True)
    salt = Column(String(64), nullable=False)
    qr_code_data = Column(Text, nullable=False)  # Raw QR payload / token string
    qr_image_base64 = Column(Text, nullable=True) # Data URI of generated QR image

    status = Column(String(50), default=PackageStatus.CREATED, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="packages")
    shop = relationship("Shop", back_populates="packages")
    shipper = relationship("User", back_populates="shipper_packages", foreign_keys=[shipper_id])
    disputes = relationship("Dispute", back_populates="package")


class EscrowWallet(Base):
    __tablename__ = "escrow_wallets"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    amount = Column(Float, nullable=False)
    commission_fee = Column(Float, default=0.0)
    net_payout = Column(Float, default=0.0)
    status = Column(String(50), default=EscrowStatus.HELD, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    order = relationship("Order", back_populates="escrow")
    shop = relationship("Shop", back_populates="escrow_wallets")


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), default=DisputeStatus.OPEN, index=True)
    proof_image = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="disputes")
    package = relationship("Package", back_populates="disputes")
    reporter = relationship("User", back_populates="disputes")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5
    comment = Column(Text, nullable=True)
    media_urls = Column(Text, nullable=True)
    is_verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="reviews")
    buyer = relationship("User", back_populates="reviews")
    order = relationship("Order", back_populates="reviews")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    requested_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # TOKEN_GENERATED, HANDSHAKE_PICKUP, HANDSHAKE_DELIVERY, ESCROW_LOCKED, ESCROW_RELEASED, DISPUTE_FILED, FRAUD_FLAGGED
    order_id = Column(Integer, nullable=True)
    package_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
