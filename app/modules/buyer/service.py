import datetime
import json
import base64
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Package, Order, Shop, User, PackageStatus, OrderStatus, AuditLog, EscrowWallet, EscrowStatus
from app.security import verify_package_token

def process_buyer_verification(db: Session, buyer: User, qr_token: str, notes: str = None):
    # 1. Parse token payload
    try:
        raw_json = base64.urlsafe_b64decode(qr_token.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)
        order_id = payload.get("order_id")
        shop_id = payload.get("shop_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid QR Code payload format")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Anti-IDOR Guardrail: Ensure buyer is the actual purchaser
    if order.buyer_id != buyer.id and buyer.role != "Admin":
        raise HTTPException(status_code=403, detail="Security Exception: You are not authorized to verify this order")

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Origin shop not found")

    # 2. Cryptographic Anti-Tamper Verification
    verification = verify_package_token(qr_token, shop.shop_secret)
    if not verification["valid"]:
        # Log tampering attempt
        audit = AuditLog(
            event_type="TAMPER_DETECTED",
            order_id=order_id,
            user_id=buyer.id,
            details=f"Buyer verification FAILED! Possible counterfeit/swapped parcel: {verification['error']}"
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"CẢNH BÁO AN TOÀN: Tem QR không hợp lệ hoặc đã bị làm giả/tráo đổi! ({verification['error']})"
        )

    # 3. Locate Package
    package = db.query(Package).filter(Package.order_id == order_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package record missing")

    if package.status == PackageStatus.DELIVERED and order.status == OrderStatus.DELIVERED_VERIFIED:
        return {
            "success": True,
            "message": "Package was already verified and delivered previously.",
            "package_id": package.id,
            "order_id": order.id,
            "status": package.status,
            "order_status": order.status,
            "timestamp": package.verified_at.isoformat() if package.verified_at else None
        }

    # Verify package was in transit
    if package.status != PackageStatus.PICKED_UP:
        raise HTTPException(
            status_code=400,
            detail=f"Kiện hàng chưa ở trạng thái đang giao (Trạng thái hiện tại: {package.status})"
        )

    # 4. Handshake 2: Verify Delivery Authenticity
    now = datetime.datetime.utcnow()
    package.status = PackageStatus.DELIVERED
    package.verified_at = now
    order.status = OrderStatus.DELIVERED_VERIFIED

    # 5. Escrow Release Automation (Module 6 Trigger)
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order.id).first()
    escrow_released = False
    payout_amount = 0.0

    if escrow and escrow.status == EscrowStatus.HELD:
        # Calculate platform commission and net seller payout
        commission_rate = shop.commission_rate or 0.05
        commission_fee = round(escrow.amount * commission_rate, 2)
        net_payout = round(escrow.amount - commission_fee, 2)
        
        escrow.commission_fee = commission_fee
        escrow.net_payout = net_payout
        escrow.status = EscrowStatus.RELEASED
        
        # Credit seller wallet
        shop.wallet_balance += net_payout
        escrow_released = True
        payout_amount = net_payout

        # Log escrow release
        audit_escrow = AuditLog(
            event_type="ESCROW_RELEASED",
            order_id=order.id,
            package_id=package.id,
            user_id=buyer.id,
            details=json.dumps({
                "action": "Automated Escrow Fund Release on Verified Delivery",
                "gross_amount": escrow.amount,
                "platform_commission": commission_fee,
                "net_payout_to_seller": net_payout,
                "shop_id": shop.id,
                "shop_name": shop.shop_name
            })
        )
        db.add(audit_escrow)

    # 6. Audit Handshake 2
    audit_delivery = AuditLog(
        event_type="HANDSHAKE_DELIVERY",
        order_id=order.id,
        package_id=package.id,
        user_id=buyer.id,
        details=json.dumps({
            "action": "Buyer scanned physical QR parcel on arrival (Handshake 2)",
            "buyer_name": buyer.full_name,
            "shop_name": shop.shop_name,
            "anti_tamper_verified": True,
            "escrow_released": escrow_released,
            "payout_amount": payout_amount
        })
    )
    db.add(audit_delivery)

    db.commit()
    db.refresh(package)
    db.refresh(order)

    return {
        "success": True,
        "message": "XÁC THỰC THÀNH CÔNG! Kiện hàng chính hãng từ nhà bán, nguyên vẹn không bị tráo đổi. Tiền ký quỹ đã được giải ngân an toàn cho Shop.",
        "package_id": package.id,
        "order_id": order.id,
        "status": package.status,
        "order_status": order.status,
        "timestamp": now.isoformat(),
        "escrow_released": escrow_released,
        "net_payout": payout_amount
    }
