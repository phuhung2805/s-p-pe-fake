from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Order, Package, Shop, UserRole
from app.schemas import QRVerificationRequest, OrderResponse
from app.modules.auth.dependencies import require_role
from app.modules.buyer.service import process_buyer_verification

router = APIRouter(prefix="/api/buyer", tags=["Module 4: Buyer Safe Verification"])

@router.get("/orders")
def get_buyer_orders(
    current_user: User = Depends(require_role([UserRole.BUYER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Returns list of orders placed by the current buyer with live tracking details.
    """
    orders = db.query(Order).filter(Order.buyer_id == current_user.id).order_by(Order.created_at.desc()).all()
    results = []
    for ord in orders:
        shop = db.query(Shop).filter(Shop.id == ord.shop_id).first()
        pkg = db.query(Package).filter(Package.order_id == ord.id).first()
        
        results.append({
            "id": ord.id,
            "shop_id": ord.shop_id,
            "shop_name": shop.shop_name if shop else "Đa gian hàng",
            "total_amount": ord.total_amount,
            "shipping_fee": ord.shipping_fee,
            "final_amount": ord.final_amount,
            "status": ord.status,
            "shipping_address": ord.shipping_address,
            "masked_phone": ord.masked_phone,
            "payment_method": ord.payment_method,
            "created_at": ord.created_at.isoformat(),
            "items": [
                {
                    "id": it.id,
                    "product_id": it.product_id,
                    "product_name": it.product.name if it.product else f"Sản phẩm #{it.product_id}",
                    "quantity": it.quantity,
                    "unit_price": it.unit_price
                } for it in ord.items
            ],
            "package": {
                "id": pkg.id,
                "status": pkg.status,
                "qr_code_data": pkg.qr_code_data,
                "qr_image_base64": pkg.qr_image_base64,
                "created_at": pkg.created_at.isoformat(),
                "verified_at": pkg.verified_at.isoformat() if pkg.verified_at else None
            } if pkg else None
        })
    return results

@router.post("/verify-package")
def buyer_verify_package(
    req: QRVerificationRequest,
    current_user: User = Depends(require_role([UserRole.BUYER])),
    db: Session = Depends(get_db)
):
    """
    Handshake 2: Buyer scans physical QR code on parcel to verify authenticity and release escrow funds.
    """
    return process_buyer_verification(db, current_user, req.qr_token, req.notes)
