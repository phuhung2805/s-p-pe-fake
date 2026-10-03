import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

# ----------------- Auth & User Schemas -----------------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    phone: Optional[str] = None
    role: str = "Buyer"  # Admin, Shop, Shipper, Buyer

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    email: str
    full_name: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    fraud_score: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# ----------------- Shop Schemas -----------------
class ShopCreate(BaseModel):
    shop_name: str
    address: str
    latitude: Optional[float] = 21.0285
    longitude: Optional[float] = 105.8542
    commission_rate: Optional[float] = 0.05

class ShopResponse(BaseModel):
    id: int
    owner_id: int
    shop_name: str
    address: str
    latitude: float
    longitude: float
    commission_rate: float
    wallet_balance: float

    class Config:
        from_attributes = True

# ----------------- Product Schemas -----------------
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock_quantity: int = Field(..., ge=0)
    category: str
    images: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    description: Optional[str] = None
    price: float
    stock_quantity: int
    category: str
    images: Optional[str] = None
    shop_name: Optional[str] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True

# ----------------- Cart & Checkout Schemas -----------------
class CartItemInput(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class CheckoutRequest(BaseModel):
    items: List[CartItemInput]
    shipping_address: str
    phone: str
    buyer_latitude: Optional[float] = 21.0300
    buyer_longitude: Optional[float] = 105.8500
    payment_method: str = "WALLET_ESCROW"  # COD, WALLET_ESCROW, VNPAY_ESCROW, MOMO_ESCROW

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    status: str

    class Config:
        from_attributes = True

class PackageResponse(BaseModel):
    id: int
    order_id: int
    shop_id: int
    shipper_id: Optional[int] = None
    status: str
    qr_code_data: str
    qr_image_base64: Optional[str] = None
    created_at: datetime.datetime
    verified_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    buyer_id: int
    shop_id: Optional[int] = None
    shop_name: Optional[str] = None
    total_amount: float
    shipping_fee: float
    final_amount: float
    status: str
    shipping_address: str
    masked_phone: Optional[str] = None
    payment_method: str
    created_at: datetime.datetime
    items: List[OrderItemResponse] = []
    packages: List[PackageResponse] = []

    class Config:
        from_attributes = True

# ----------------- Verification & Handshake Schemas -----------------
class QRVerificationRequest(BaseModel):
    qr_token: str
    notes: Optional[str] = None

class HandshakeResult(BaseModel):
    success: bool
    message: str
    package_id: int
    order_id: int
    status: str
    timestamp: datetime.datetime

# ----------------- Escrow Schemas -----------------
class EscrowResponse(BaseModel):
    id: int
    order_id: int
    buyer_id: int
    shop_id: int
    amount: float
    commission_fee: float
    net_payout: float
    status: str
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# ----------------- Dispute Schemas -----------------
class DisputeCreate(BaseModel):
    order_id: int
    package_id: Optional[int] = None
    reason: str
    notes: Optional[str] = None
    proof_image: Optional[str] = None

class DisputeResolveRequest(BaseModel):
    status: str  # RESOLVED, FRAUD_FLAGGED
    action: str  # REFUND_BUYER, RELEASE_TO_SHOP, FLAG_FRAUD
    admin_notes: Optional[str] = None

class DisputeResponse(BaseModel):
    id: int
    order_id: int
    package_id: Optional[int] = None
    reporter_id: int
    reporter_name: Optional[str] = None
    reason: str
    status: str
    proof_image: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

# ----------------- Review Schemas -----------------
class ReviewCreate(BaseModel):
    product_id: int
    order_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    media_urls: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    product_id: int
    buyer_id: int
    buyer_name: Optional[str] = None
    order_id: int
    rating: int
    comment: Optional[str] = None
    is_verified_purchase: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# ----------------- Admin Analytics -----------------
class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    order_id: Optional[int] = None
    package_id: Optional[int] = None
    user_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AdminDashboardStats(BaseModel):
    total_gmv: float
    total_commission: float
    active_sellers: int
    active_shippers: int
    total_orders: int
    total_packages: int
    safe_delivery_rate: float
    dispute_count: int
    flagged_fraud_count: int
