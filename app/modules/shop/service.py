import json
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Shop, Product, Order, OrderStatus, Package, PackageStatus, AuditLog, User
from app.security import generate_package_token
from app.schemas import ProductCreate

def get_or_create_shop_for_user(db: Session, user: User) -> Shop:
    shop = db.query(Shop).filter(Shop.owner_id == user.id).first()
    if not shop:
        import secrets
        shop = Shop(
            owner_id=user.id,
            shop_name=f"Shop {user.full_name}",
            address="Hà Nội, Việt Nam",
            latitude=21.0285,
            longitude=105.8542,
            commission_rate=0.05,
            wallet_balance=0.0,
            shop_secret=secrets.token_hex(32)
        )
        db.add(shop)
        db.commit()
        db.refresh(shop)
    return shop

def pack_order_and_generate_qr(db: Session, shop: Shop, order_id: int):
    # Verify order belongs to this shop
    order = db.query(Order).filter(Order.id == order_id, Order.shop_id == shop.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this shop")
    
    if order.status not in [OrderStatus.PENDING, OrderStatus.PAID_ESCROW]:
        raise HTTPException(status_code=400, detail=f"Order status '{order.status}' cannot be packed")

    # Check if a package already exists
    existing_package = db.query(Package).filter(Package.order_id == order.id).first()
    if existing_package:
        return existing_package, order

    # Generate HMAC-SHA256 Token & dynamic QR Code
    token_str, salt, sig, qr_base64 = generate_package_token(
        order_id=order.id,
        shop_id=shop.id,
        shop_secret=shop.shop_secret
    )

    package = Package(
        order_id=order.id,
        shop_id=shop.id,
        package_token_hash=sig,
        salt=salt,
        qr_code_data=token_str,
        qr_image_base64=qr_base64,
        status=PackageStatus.CREATED
    )
    db.add(package)
    
    # Update order state machine to PACKED
    order.status = OrderStatus.PACKED
    
    # Immutable audit log
    audit = AuditLog(
        event_type="TOKEN_GENERATED",
        order_id=order.id,
        package_id=package.id,
        user_id=shop.owner_id,
        details=json.dumps({
            "action": "Generated Anti-Tamper Packaging QR",
            "salt": salt,
            "signature_prefix": sig[:12] + "...",
            "shop_name": shop.shop_name
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(package)
    db.refresh(order)
    return package, order
