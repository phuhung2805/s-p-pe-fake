from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Package, Order, Shop, PackageStatus, OrderStatus, UserRole
from app.schemas import QRVerificationRequest
from app.modules.auth.dependencies import require_role
from app.modules.shipper.service import process_shipper_pickup

router = APIRouter(prefix="/api/shipper", tags=["Module 3: Shipper Dispatch App"])

@router.get("/available-packages")
def get_available_packages_for_pickup(
    current_user: User = Depends(require_role([UserRole.SHIPPER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Lists ready-to-ship packages waiting for a shipper at shop warehouses.
    """
    packages = db.query(Package).filter(
        Package.status == PackageStatus.CREATED
    ).all()

    results = []
    for pkg in packages:
        order = db.query(Order).filter(Order.id == pkg.order_id).first()
        shop = db.query(Shop).filter(Shop.id == pkg.shop_id).first()
        if order and shop:
            results.append({
                "package_id": pkg.id,
                "order_id": order.id,
                "shop_name": shop.shop_name,
                "shop_address": shop.address,
                "delivery_address": order.shipping_address,
                "masked_phone": order.masked_phone,
                "final_amount": order.final_amount,
                "payment_method": order.payment_method,
                "qr_code_data": pkg.qr_code_data,
                "qr_image_base64": pkg.qr_image_base64,
                "created_at": pkg.created_at.isoformat()
            })
    return results

@router.get("/active-deliveries")
def get_shipper_active_deliveries(
    current_user: User = Depends(require_role([UserRole.SHIPPER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Lists deliveries currently in transit with this shipper.
    """
    packages = db.query(Package).filter(
        Package.shipper_id == current_user.id,
        Package.status.in_([PackageStatus.PICKED_UP, PackageStatus.DELIVERED])
    ).order_by(Package.created_at.desc()).all()

    results = []
    for pkg in packages:
        order = db.query(Order).filter(Order.id == pkg.order_id).first()
        shop = db.query(Shop).filter(Shop.id == pkg.shop_id).first()
        if order:
            results.append({
                "package_id": pkg.id,
                "order_id": order.id,
                "shop_name": shop.shop_name if shop else "N/A",
                "shop_address": shop.address if shop else "N/A",
                "delivery_address": order.shipping_address,
                "masked_phone": order.masked_phone,
                "package_status": pkg.status,
                "order_status": order.status,
                "final_amount": order.final_amount,
                "payment_method": order.payment_method,
                "qr_code_data": pkg.qr_code_data,
                "created_at": pkg.created_at.isoformat(),
                "verified_at": pkg.verified_at.isoformat() if pkg.verified_at else None
            })
    return results

@router.post("/handshake-pickup")
def shipper_handshake_pickup(
    req: QRVerificationRequest,
    current_user: User = Depends(require_role([UserRole.SHIPPER])),
    db: Session = Depends(get_db)
):
    """
    Handshake 1: Shipper scans physical QR code on package at the Shop warehouse.
    """
    return process_shipper_pickup(db, current_user, req.qr_token, req.notes)
