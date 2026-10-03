from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, EscrowWallet, UserRole
from app.schemas import EscrowResponse
from app.modules.auth.dependencies import require_role
from app.modules.escrow.service import release_escrow_funds, refund_escrow_to_buyer

router = APIRouter(prefix="/api/escrow", tags=["Module 6: Payment & Escrow Lock"])

@router.get("/order/{order_id}", response_model=EscrowResponse)
def get_order_escrow_status(
    order_id: int,
    current_user: User = Depends(require_role([UserRole.BUYER, UserRole.SHOP, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order_id).first()
    if not escrow:
        raise HTTPException(status_code=404, detail="No escrow record found for this order")
    
    # IDOR check: only buyer, shop owner, or admin can inspect escrow details
    if current_user.role == UserRole.BUYER and escrow.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if current_user.role == UserRole.SHOP:
        shop = current_user.shops[0] if current_user.shops else None
        if not shop or shop.id != escrow.shop_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    return escrow

@router.post("/order/{order_id}/release", response_model=EscrowResponse)
def manual_escrow_release(
    order_id: int,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Admin manual release of escrow funds in case of dispute resolution.
    """
    return release_escrow_funds(db, order_id, admin_user_id=current_user.id)

@router.post("/order/{order_id}/refund", response_model=EscrowResponse)
def manual_escrow_refund(
    order_id: int,
    reason: str = "Admin approved refund",
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Admin manual refund of escrow funds back to buyer.
    """
    return refund_escrow_to_buyer(db, order_id, admin_user_id=current_user.id, reason=reason)
