from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Review, Order, OrderStatus, User, OrderItem
from app.schemas import ReviewCreate

def create_verified_review(db: Session, buyer: User, req: ReviewCreate):
    # 1. Anti-Fake Guardrail Check
    order = db.query(Order).filter(Order.id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.buyer_id != buyer.id:
        raise HTTPException(status_code=403, detail="Chỉ người mua đơn hàng này mới được phép đánh giá")

    if order.status != OrderStatus.DELIVERED_VERIFIED and order.status != OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="BẢO VỆ CHỐNG ĐÁNH GIÁ ẢO: Bạn chỉ có thể đánh giá sau khi đã nhận và quét mã QR xác thực kiện hàng thành công (DELIVERED_VERIFIED)!"
        )

    # Verify that the order actually contained this product
    item_in_order = db.query(OrderItem).filter(
        OrderItem.order_id == order.id,
        OrderItem.product_id == req.product_id
    ).first()
    if not item_in_order:
        raise HTTPException(status_code=400, detail="Sản phẩm này không nằm trong đơn hàng đã mua")

    # Check for duplicate review
    existing = db.query(Review).filter(
        Review.order_id == req.order_id,
        Review.product_id == req.product_id,
        Review.buyer_id == buyer.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bạn đã đánh giá sản phẩm này cho đơn hàng này rồi")

    review = Review(
        product_id=req.product_id,
        buyer_id=buyer.id,
        order_id=order.id,
        rating=req.rating,
        comment=req.comment,
        media_urls=req.media_urls,
        is_verified_purchase=True
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
