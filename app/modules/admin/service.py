from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Order, OrderStatus, Package, PackageStatus, EscrowWallet, EscrowStatus, User, UserRole, Dispute, DisputeStatus, AuditLog
from app.schemas import AdminDashboardStats

def get_admin_dashboard_metrics(db: Session) -> AdminDashboardStats:
    # 1. Total GMV: sum of final_amount of valid orders (excluding cancelled)
    gmv = db.query(func.sum(Order.final_amount)).filter(Order.status != OrderStatus.CANCELLED).scalar() or 0.0

    # 2. Total Commission: sum of commission_fee in EscrowWallets
    commission = db.query(func.sum(EscrowWallet.commission_fee)).filter(
        EscrowWallet.status == EscrowStatus.RELEASED
    ).scalar() or 0.0

    # 3. Active counts
    active_sellers = db.query(User).filter(User.role == UserRole.SHOP).count()
    active_shippers = db.query(User).filter(User.role == UserRole.SHIPPER).count()
    total_orders = db.query(Order).count()
    total_packages = db.query(Package).count()

    # 4. Safe Delivery Rate (%)
    delivered_count = db.query(Package).filter(Package.status == PackageStatus.DELIVERED).count()
    verified_count = db.query(Package).filter(Package.verified_at != None).count()
    safe_rate = 100.0 if delivered_count == 0 else round((verified_count / delivered_count) * 100.0, 1)

    # 5. Fraud and Dispute indicators
    dispute_count = db.query(Dispute).count()
    flagged_fraud_count = db.query(User).filter(User.fraud_score >= 20).count()

    return AdminDashboardStats(
        total_gmv=round(gmv, 2),
        total_commission=round(commission, 2),
        active_sellers=active_sellers,
        active_shippers=active_shippers,
        total_orders=total_orders,
        total_packages=total_packages,
        safe_delivery_rate=safe_rate,
        dispute_count=dispute_count,
        flagged_fraud_count=flagged_fraud_count
    )
