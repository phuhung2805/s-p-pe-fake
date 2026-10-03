from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Review, User, UserRole
from app.schemas import ReviewCreate, ReviewResponse
from app.modules.auth.dependencies import require_role
from app.modules.review.service import create_verified_review

router = APIRouter(prefix="/api/reviews", tags=["Module 9: Verified Purchase Reviews"])

@router.post("", response_model=ReviewResponse)
def submit_review(
    req: ReviewCreate,
    current_user: User = Depends(require_role([UserRole.BUYER])),
    db: Session = Depends(get_db)
):
    """
    Submits a review with strict verification of actual delivered purchase.
    """
    review = create_verified_review(db, current_user, req)
    return ReviewResponse(
        id=review.id,
        product_id=review.product_id,
        buyer_id=review.buyer_id,
        buyer_name=current_user.full_name,
        order_id=review.order_id,
        rating=review.rating,
        comment=review.comment,
        is_verified_purchase=review.is_verified_purchase,
        created_at=review.created_at
    )

@router.get("/product/{product_id}", response_model=List[ReviewResponse])
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.product_id == product_id).order_by(Review.created_at.desc()).all()
    results = []
    for r in reviews:
        results.append(ReviewResponse(
            id=r.id,
            product_id=r.product_id,
            buyer_id=r.buyer_id,
            buyer_name=r.buyer.full_name if r.buyer else "Người mua",
            order_id=r.order_id,
            rating=r.rating,
            comment=r.comment,
            is_verified_purchase=r.is_verified_purchase,
            created_at=r.created_at
        ))
    return results
