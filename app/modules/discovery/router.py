from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Product, Shop, Order, Package
from app.schemas import ProductResponse
from app.modules.order.service import calculate_haversine_distance
from app.modules.discovery.privacy import mask_phone_number, mask_street_address

router = APIRouter(prefix="/api/discovery", tags=["Module 7: Discovery & Privacy Masking"])


@router.get("/autocomplete")
def autocomplete_suggestions(
        q: str = Query(..., min_length=1, description="Từ khóa gợi ý"),
        db: Session = Depends(get_db)
):
    """
    Bổ sung theo yêu cầu Module 7: Trả về danh sách gợi ý tên sản phẩm (Autocomplete)
    """
    products = db.query(Product.name, Product.category).filter(
        Product.name.ilike(f"%{q}%")
    ).limit(8).all()

    suggestions = [{"name": p.name, "category": p.category} for p in products]
    return {"suggestions": suggestions}


@router.get("/products", response_model=List[ProductResponse])
def search_and_discover_products(
        q: Optional[str] = Query(None, description="Search keyword"),
        category: Optional[str] = Query(None, description="Category filter"),
        min_price: Optional[float] = Query(None, description="Min price"),
        max_price: Optional[float] = Query(None, description="Max price"),
        buyer_lat: Optional[float] = Query(None, description="Buyer latitude for geo-sorting"),
        buyer_lon: Optional[float] = Query(None, description="Buyer longitude for geo-sorting"),
        sort_by: Optional[str] = Query("distance", description="distance, price_asc, price_desc"),
        db: Session = Depends(get_db)
):
    query = db.query(Product).join(Shop, Product.shop_id == Shop.id)

    if q:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%")
            )
        )
    if category and category != "ALL":
        query = query.filter(Product.category == category)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    products = query.all()
    results = []

    for p in products:
        shop = p.shop
        dist = None
        if buyer_lat is not None and buyer_lon is not None and shop.latitude and shop.longitude:
            dist = calculate_haversine_distance(buyer_lat, buyer_lon, shop.latitude, shop.longitude)

        results.append(ProductResponse(
            id=p.id,
            shop_id=p.shop_id,
            name=p.name,
            description=p.description,
            price=p.price,
            stock_quantity=p.stock_quantity,
            category=p.category,
            images=p.images,
            shop_name=shop.shop_name,
            distance_km=dist
        ))

    # Sort results
    if sort_by == "distance" and buyer_lat is not None:
        results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else 99999))
    elif sort_by == "price_asc":
        results.sort(key=lambda x: x.price)
    elif sort_by == "price_desc":
        results.sort(key=lambda x: x.price, reverse=True)

    return results


@router.get("/waybill/{order_id}")
def generate_privacy_waybill(order_id: int, db: Session = Depends(get_db)):
    """
    Waybill (Vận đơn / Tem niêm phong giao hàng) with automatic data privacy masking:
    Redacts personal phone and home address for physical parcel printing.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    shop = db.query(Shop).filter(Shop.id == order.shop_id).first()
    package = db.query(Package).filter(Package.order_id == order.id).first()

    return {
        "waybill_id": f"WB-{order.id:06d}",
        "order_id": order.id,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "sender": {
            "shop_name": shop.shop_name if shop else "Chính Hãng",
            "address": shop.address if shop else "Kho tổng",
        },
        "recipient": {
            "name": order.buyer.full_name if order.buyer else "Khách hàng",
            "masked_phone": mask_phone_number(order.masked_phone or order.buyer.phone or "0912345678"),
            "masked_address": mask_street_address(order.shipping_address)
        },
        "items": [
            {
                "product_name": it.product.name if it.product else f"Sản phẩm #{it.product_id}",
                "quantity": it.quantity
            } for it in order.items
        ],
        "final_amount": order.final_amount,
        "payment_method": order.payment_method,
        "anti_tamper_qr": {
            "qr_token": package.qr_code_data if package else None,
            "qr_image_base64": package.qr_image_base64 if package else None,
            "security_hash": package.package_token_hash[:16] + "..." if package else None
        }
    }