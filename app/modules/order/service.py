import math
import json
from collections import defaultdict
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Product, Order, OrderItem, Shop, User, EscrowWallet, OrderStatus, EscrowStatus, AuditLog, PaymentMethod
from app.schemas import CheckoutRequest
from app.modules.discovery.privacy import mask_phone_number, mask_street_address

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in kilometers between two points on Earth.
    """
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def process_checkout(db: Session, buyer: User, req: CheckoutRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 1. Group items by shop_id to support multi-vendor order split
    items_by_shop = defaultdict(list)
    product_map = {}

    for item in req.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product #{item.product_id} not found")
        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Sản phẩm '{product.name}' chỉ còn {product.stock_quantity} trong kho")
        
        items_by_shop[product.shop_id].append({
            "product": product,
            "quantity": item.quantity,
            "unit_price": product.price
        })
        product_map[product.id] = product

    created_orders = []
    masked_phone = mask_phone_number(req.phone or buyer.phone or "0900000000")

    # 2. Iterate each shop to create a distinct sub-order
    for shop_id, shop_items in items_by_shop.items():
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            continue

        # Subtotal calculation
        subtotal = sum(it["quantity"] * it["unit_price"] for it in shop_items)

        # Distance & Shipping Fee calculation
        distance_km = calculate_haversine_distance(
            shop.latitude or 21.0285, shop.longitude or 105.8542,
            req.buyer_latitude or 21.0300, req.buyer_longitude or 105.8500
        )
        shipping_fee = 15000.0 + max(0.0, distance_km * 2000.0)
        shipping_fee = round(shipping_fee, -2) # Round to nearest 100 VND
        final_amount = subtotal + shipping_fee

        # Initial status based on payment method
        initial_status = OrderStatus.PAID_ESCROW if req.payment_method != PaymentMethod.COD else OrderStatus.PENDING

        new_order = Order(
            buyer_id=buyer.id,
            shop_id=shop.id,
            total_amount=subtotal,
            shipping_fee=shipping_fee,
            final_amount=final_amount,
            status=initial_status,
            shipping_address=req.shipping_address,
            buyer_latitude=req.buyer_latitude,
            buyer_longitude=req.buyer_longitude,
            masked_phone=masked_phone,
            payment_method=req.payment_method
        )
        db.add(new_order)
        db.flush()  # To populate new_order.id

        # Add Order Items & decrement stock
        for it in shop_items:
            prod = it["product"]
            prod.stock_quantity -= it["quantity"]
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=prod.id,
                shop_id=shop.id,
                quantity=it["quantity"],
                unit_price=it["unit_price"]
            )
            db.add(order_item)

        # Module 6 Escrow Wallet Creation (Lock funds)
        escrow = EscrowWallet(
            order_id=new_order.id,
            buyer_id=buyer.id,
            shop_id=shop.id,
            amount=final_amount,
            commission_fee=round(final_amount * (shop.commission_rate or 0.05), 2),
            net_payout=round(final_amount * (1 - (shop.commission_rate or 0.05)), 2),
            status=EscrowStatus.HELD
        )
        db.add(escrow)

        # Audit Log
        audit = AuditLog(
            event_type="ESCROW_LOCKED",
            order_id=new_order.id,
            user_id=buyer.id,
            details=json.dumps({
                "action": "Order created & escrow locked",
                "shop_id": shop.id,
                "amount": final_amount,
                "payment_method": req.payment_method,
                "distance_km": distance_km
            })
        )
        db.add(audit)

        created_orders.append({
            "order_id": new_order.id,
            "shop_id": shop.id,
            "shop_name": shop.shop_name,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "final_amount": final_amount,
            "status": new_order.status,
            "distance_km": distance_km,
            "item_count": len(shop_items)
        })

    db.commit()
    return created_orders
