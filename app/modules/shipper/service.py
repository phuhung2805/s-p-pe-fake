import datetime
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Package, Order, Shop, User, PackageStatus, OrderStatus, AuditLog
from app.security import verify_package_token

def process_shipper_pickup(db: Session, shipper: User, qr_token: str, notes: str = None):
    # 1. Parse payload to find order_id and shop_id
    import base64
    try:
        raw_json = base64.urlsafe_b64decode(qr_token.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)
        order_id = payload.get("order_id")
        shop_id = payload.get("shop_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid QR Code payload format")

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop registered on QR token not found")

    # 2. Cryptographic Anti-Tamper Verification
    verification = verify_package_token(qr_token, shop.shop_secret)
    if not verification["valid"]:
        # Log tampering attempt
        audit = AuditLog(
            event_type="TAMPER_DETECTED",
            order_id=order_id,
            user_id=shipper.id,
            details=f"Tampered QR token scanned during Shipper Pickup: {verification['error']}"
        )
        db.add(audit)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Anti-Tamper Security Alert: {verification['error']}")

    # 3. Locate Package and Order
    package = db.query(Package).filter(Package.order_id == order_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package record not found in system")

    if package.status != PackageStatus.CREATED:
        raise HTTPException(
            status_code=400,
            detail=f"Package is in status '{package.status}', cannot perform warehouse pickup"
        )

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Associated order not found")

    # 4. Perform Handshake 1: Transition states
    package.shipper_id = shipper.id
    package.status = PackageStatus.PICKED_UP
    order.status = OrderStatus.IN_TRANSIT

    # 5. Audit Logging
    audit = AuditLog(
        event_type="HANDSHAKE_PICKUP",
        order_id=order.id,
        package_id=package.id,
        user_id=shipper.id,
        details=json.dumps({
            "action": "Shipper scanned package at Shop Warehouse (Handshake 1)",
            "shipper_name": shipper.full_name,
            "shipper_phone": shipper.phone,
            "shop_name": shop.shop_name,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(package)
    db.refresh(order)

    return {
        "success": True,
        "message": f"Handshake 1 Verified! Package #{package.id} picked up from {shop.shop_name}. Order is now IN_TRANSIT.",
        "package_id": package.id,
        "order_id": order.id,
        "status": package.status,
        "order_status": order.status,
        "delivery_address": order.shipping_address,
        "masked_phone": order.masked_phone
    }
