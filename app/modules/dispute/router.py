from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Dispute, UserRole
from app.schemas import DisputeCreate, DisputeResponse, DisputeResolveRequest
from app.modules.auth.dependencies import require_role
from app.modules.dispute.service import file_dispute, resolve_dispute

router = APIRouter(prefix="/api/disputes", tags=["Module 8: Anti-Fraud & Disputes"])

@router.post("", response_model=DisputeResponse)
def submit_dispute(
    req: DisputeCreate,
    current_user: User = Depends(require_role([UserRole.BUYER])),
    db: Session = Depends(get_db)
):
    """
    Buyer files a dispute on a damaged parcel or swapped content.
    Escrow funds are immediately frozen.
    """
    dispute = file_dispute(db, current_user, req)
    return DisputeResponse(
        id=dispute.id,
        order_id=dispute.order_id,
        package_id=dispute.package_id,
        reporter_id=dispute.reporter_id,
        reporter_name=current_user.full_name,
        reason=dispute.reason,
        status=dispute.status,
        proof_image=dispute.proof_image,
        notes=dispute.notes,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at
    )

@router.get("", response_model=List[DisputeResponse])
def get_all_disputes(
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SHOP])),
    db: Session = Depends(get_db)
):
    query = db.query(Dispute)
    if current_user.role == UserRole.SHOP:
        shop = current_user.shops[0] if current_user.shops else None
        if shop:
            query = query.join(Dispute.order).filter(Dispute.order.has(shop_id=shop.id))
        else:
            return []

    disputes = query.order_by(Dispute.created_at.desc()).all()
    results = []
    for d in disputes:
        results.append(DisputeResponse(
            id=d.id,
            order_id=d.order_id,
            package_id=d.package_id,
            reporter_id=d.reporter_id,
            reporter_name=d.reporter.full_name if d.reporter else "Buyer",
            reason=d.reason,
            status=d.status,
            proof_image=d.proof_image,
            notes=d.notes,
            created_at=d.created_at,
            resolved_at=d.resolved_at
        ))
    return results

@router.post("/{dispute_id}/resolve", response_model=DisputeResponse)
def resolve_order_dispute(
    dispute_id: int,
    req: DisputeResolveRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Admin resolves dispute: refunds buyer, releases to shop, or flags fraud.
    """
    dispute = resolve_dispute(db, dispute_id, current_user, req)
    return DisputeResponse(
        id=dispute.id,
        order_id=dispute.order_id,
        package_id=dispute.package_id,
        reporter_id=dispute.reporter_id,
        reporter_name=dispute.reporter.full_name if dispute.reporter else "Buyer",
        reason=dispute.reason,
        status=dispute.status,
        proof_image=dispute.proof_image,
        notes=dispute.notes,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at
    )
