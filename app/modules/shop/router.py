from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Shop, Product, Order, Package, UserRole
from app.schemas import ProductCreate, ProductResponse, ShopResponse, OrderResponse, PackageResponse
from app.modules.auth.dependencies import require_role
from app.modules.shop.service import get_or_create_shop_for_user, pack_order_and_generate_qr

router = APIRouter(prefix="/api/shop", tags=["Module 2: Seller & Anti-Tamper QR"])

@router.get("/profile", response_model=ShopResponse)
def get_shop_profile(
    current_user: User = Depends(require_role([UserRole.SHOP, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    shop = get_or_create_shop_for_user(db, current_user)
    return shop

@router.get("/products", response_model=List[ProductResponse])
def get_shop_products(
    current_user: User = Depends(require_role([UserRole.SHOP, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    shop = get_or_create_shop_for_user(db, current_user)
    products = db.query(Product).filter(Product.shop_id == shop.id).all()
    res = []
    for p in products:
        res.append(ProductResponse(
            id=p.id,
            shop_id=p.shop_id,
            name=p.name,
            description=p.description,
            price=p.price,
            stock_quantity=p.stock_quantity,
            category=p.category,
            images=p.images,
            shop_name=shop.shop_name
        ))
    return res

@router.post("/products", response_model=ProductResponse)
def create_product(
    req: ProductCreate,
    current_user: User = Depends(require_role([UserRole.SHOP])),
    db: Session = Depends(get_db)
):
    shop = get_or_create_shop_for_user(db, current_user)
    product = Product(
        shop_id=shop.id,
        name=req.name,
        description=req.description,
        price=req.price,
        stock_quantity=req.stock_quantity,
        category=req.category,
        images=req.images
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductResponse(
        id=product.id,
        shop_id=product.shop_id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock_quantity=product.stock_quantity,
        category=product.category,
        images=product.images,
        shop_name=shop.shop_name
    )

@router.get("/orders")
def get_shop_orders(
    current_user: User = Depends(require_role([UserRole.SHOP])),
    db: Session = Depends(get_db)
):
    shop = get_or_create_shop_for_user(db, current_user)
    orders = db.query(Order).filter(Order.shop_id == shop.id).order_by(Order.created_at.desc()).all()
    results = []
    for ord in orders:
        pkg = db.query(Package).filter(Package.order_id == ord.id).first()
        results.append({
            "id": ord.id,
            "buyer_id": ord.buyer_id,
            "shop_id": ord.shop_id,
            "total_amount": ord.total_amount,
            "shipping_fee": ord.shipping_fee,
            "final_amount": ord.final_amount,
            "status": ord.status,
            "shipping_address": ord.shipping_address,
            "masked_phone": ord.masked_phone,
            "payment_method": ord.payment_method,
            "created_at": ord.created_at.isoformat(),
            "items": [{"id": it.id, "product_id": it.product_id, "quantity": it.quantity, "unit_price": it.unit_price} for it in ord.items],
            "package": {
                "id": pkg.id,
                "status": pkg.status,
                "qr_code_data": pkg.qr_code_data,
                "qr_image_base64": pkg.qr_image_base64,
                "created_at": pkg.created_at.isoformat()
            } if pkg else None
        })
    return results

@router.post("/orders/{order_id}/pack")
def pack_order(
    order_id: int,
    current_user: User = Depends(require_role([UserRole.SHOP])),
    db: Session = Depends(get_db)
):
    shop = get_or_create_shop_for_user(db, current_user)
    package, order = pack_order_and_generate_qr(db, shop, order_id)
    return {
        "message": "Order packed successfully. Anti-tamper QR generated.",
        "package_id": package.id,
        "order_id": order.id,
        "status": order.status,
        "qr_code_data": package.qr_code_data,
        "qr_image_base64": package.qr_image_base64
    }
