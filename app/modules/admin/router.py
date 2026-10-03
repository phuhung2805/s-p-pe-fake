from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditLog, Dispute, UserRole
from app.schemas import AdminDashboardStats, AuditLogResponse, UserResponse
from app.modules.auth.dependencies import require_role
from app.modules.admin.service import get_admin_dashboard_metrics

router = APIRouter(prefix="/api/admin", tags=["Module 10: Admin & Security Dashboard"])

@router.get("/metrics", response_model=AdminDashboardStats)
def get_kpi_metrics(
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    return get_admin_dashboard_metrics(db)

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_trail(
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return logs

@router.get("/flagged-users", response_model=List[UserResponse])
def get_flagged_users(
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.fraud_score > 0).order_by(User.fraud_score.desc()).all()
    return users

@router.post("/users/{user_id}/reset-fraud-score", response_model=UserResponse)
def reset_user_fraud_score(
    user_id: int,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.fraud_score = 0
    db.commit()
    db.refresh(user)
    return user
