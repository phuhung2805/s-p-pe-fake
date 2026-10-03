from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Order, UserRole
from app.schemas import CheckoutRequest
from app.modules.auth.dependencies import require_role
from app.modules.order.service import process_checkout

router = APIRouter(prefix="/api/orders", tags=["Module 5: Cart & Multi-Vendor Split"])

@router.post("/checkout")
def checkout_cart(
    req: CheckoutRequest,
    current_user: User = Depends(require_role([UserRole.BUYER])),
    db: Session = Depends(get_db)
):
    """
    Submits unified cart, automatically splits into sub-orders grouped by shop_id,
    locks payment in escrow, and prepares packaging requests.
    """
    sub_orders = process_checkout(db, current_user, req)
    return {
        "message": f"Đặt hàng thành công! Đã tách thành {len(sub_orders)} kiện hàng tương ứng từng Shop.",
        "orders": sub_orders
    }

@router.get("/{order_id}")
def get_order_details(
    order_id: int,
    current_user: User = Depends(require_role([UserRole.BUYER, UserRole.SHOP, UserRole.SHIPPER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return {
        "id": order.id,
        "buyer_id": order.buyer_id,
        "shop_id": order.shop_id,
        "total_amount": order.total_amount,
        "shipping_fee": order.shipping_fee,
        "final_amount": order.final_amount,
        "status": order.status,
        "shipping_address": order.shipping_address,
        "masked_phone": order.masked_phone,
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product.name if it.product else "",
                "quantity": it.quantity,
                "unit_price": it.unit_price
            } for it in order.items
        ]
    }
