import datetime
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Dispute, Order, Package, EscrowWallet, User, OrderStatus, EscrowStatus, DisputeStatus, AuditLog
from app.schemas import DisputeCreate, DisputeResolveRequest

def file_dispute(db: Session, reporter: User, req: DisputeCreate):
    order = db.query(Order).filter(Order.id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    package = db.query(Package).filter(Package.order_id == order.id).first()

    # Create dispute record
    dispute = Dispute(
        order_id=order.id,
        package_id=package.id if package else None,
        reporter_id=reporter.id,
        reason=req.reason,
        notes=req.notes,
        proof_image=req.proof_image,
        status=DisputeStatus.OPEN
    )
    db.add(dispute)

    # 1. Update Order status to DISPUTED
    order.status = OrderStatus.DISPUTED

    # 2. Freeze Escrow Immediately (Lock Escrow)
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order.id).first()
    if escrow and escrow.status == EscrowStatus.HELD:
        escrow.status = EscrowStatus.DISPUTED

    # 3. Flag suspect shop and shipper with fraud warning score (+20 score)
    if order.shop and order.shop.owner:
        order.shop.owner.fraud_score += 20
    if package and package.shipper:
        package.shipper.fraud_score += 10

    # 4. Audit Log
    audit = AuditLog(
        event_type="DISPUTE_FILED",
        order_id=order.id,
        package_id=package.id if package else None,
        user_id=reporter.id,
        details=json.dumps({
            "reason": req.reason,
            "escrow_frozen": True,
            "notes": req.notes,
            "shop_fraud_score_increased": True
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(dispute)
    return dispute

def resolve_dispute(db: Session, dispute_id: int, admin_user: User, req: DisputeResolveRequest):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    order = db.query(Order).filter(Order.id == dispute.order_id).first()
    escrow = db.query(EscrowWallet).filter(EscrowWallet.order_id == order.id).first() if order else None

    dispute.status = req.status
    dispute.resolved_at = datetime.datetime.utcnow()

    if req.action == "REFUND_BUYER":
        if escrow:
            escrow.status = EscrowStatus.REFUNDED
        if order:
            order.status = OrderStatus.CANCELLED
    elif req.action == "RELEASE_TO_SHOP":
        if escrow and order and order.shop:
            commission = round(escrow.amount * (order.shop.commission_rate or 0.05), 2)
            payout = round(escrow.amount - commission, 2)
            escrow.status = EscrowStatus.RELEASED
            escrow.commission_fee = commission
            escrow.net_payout = payout
            order.shop.wallet_balance += payout
            order.status = OrderStatus.COMPLETED
    elif req.action == "FLAG_FRAUD":
        dispute.status = DisputeStatus.FRAUD_FLAGGED
        if order and order.shop and order.shop.owner:
            order.shop.owner.fraud_score += 50
        if escrow:
            escrow.status = EscrowStatus.REFUNDED
        if order:
            order.status = OrderStatus.CANCELLED

    audit = AuditLog(
        event_type="DISPUTE_RESOLVED",
        order_id=dispute.order_id,
        user_id=admin_user.id,
        details=json.dumps({
            "action": req.action,
            "dispute_id": dispute.id,
            "admin_notes": req.admin_notes
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(dispute)
    return dispute
