from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import EscrowWallet, EscrowStatus, Order, Shop, AuditLog, OrderStatus
import json

def release_escrow_funds(db: Session, order_id: int, admin_user_id: int = None):
    """
    Releases held escrow funds to the seller after deducting commission.
    """
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order_id).first()
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow record not found for this order")

    if escrow.status == EscrowStatus.RELEASED:
        return escrow

    shop = db.query(Shop).filter(Shop.id == escrow.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    commission_rate = shop.commission_rate or 0.05
    commission = round(escrow.amount * commission_rate, 2)
    payout = round(escrow.amount - commission, 2)

    escrow.commission_fee = commission
    escrow.net_payout = payout
    escrow.status = EscrowStatus.RELEASED

    # Credit shop wallet balance
    shop.wallet_balance += payout

    audit = AuditLog(
        event_type="ESCROW_RELEASED",
        order_id=order_id,
        user_id=admin_user_id,
        details=json.dumps({
            "amount": escrow.amount,
            "commission": commission,
            "net_payout": payout,
            "shop_name": shop.shop_name
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(escrow)
    return escrow

def refund_escrow_to_buyer(db: Session, order_id: int, admin_user_id: int = None, reason: str = ""):
    """
    Refunds held escrow funds back to the buyer (e.g. in dispute resolution).
    """
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order_id).first()
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow record not found")

    if escrow.status == EscrowStatus.REFUNDED:
        return escrow

    escrow.status = EscrowStatus.REFUNDED
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = OrderStatus.CANCELLED

    audit = AuditLog(
        event_type="ESCROW_REFUNDED",
        order_id=order_id,
        user_id=admin_user_id,
        details=json.dumps({
            "action": "Escrow Refund to Buyer",
            "amount": escrow.amount,
            "reason": reason
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(escrow)
    return escrow
