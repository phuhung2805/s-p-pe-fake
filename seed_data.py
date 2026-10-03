import sys
import datetime
import secrets

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from app.database import engine, SessionLocal, Base
from app.models import (
    User, Shop, Product, Order, OrderItem, Package, EscrowWallet,
    OrderStatus, PackageStatus, EscrowStatus, UserRole, PaymentMethod, AuditLog, Review
)
from app.security import hash_password, generate_package_token

def seed():
    # Re-create all tables clean
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear existing data if needed
    db.query(Review).delete()
    db.query(AuditLog).delete()
    db.query(EscrowWallet).delete()
    db.query(Package).delete()
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Product).delete()
    db.query(Shop).delete()
    db.query(User).delete()
    db.commit()

    print(">>> Seeding Users (Admin, Shop, Shipper, Buyer)...")
    # 1. Admin
    admin = User(
        email="admin@ecommerce.vn",
        password_hash=hash_password("Password123!"),
        full_name="Quản Trị Viên Hệ Thống",
        phone="0909999999",
        role=UserRole.ADMIN,
        fraud_score=0
    )

    # 2. Shop 1 (TechStore)
    shop1_user = User(
        email="shop1@techstore.vn",
        password_hash=hash_password("Password123!"),
        full_name="Nguyễn Văn Shop (TechStore)",
        phone="0901111111",
        role=UserRole.SHOP,
        fraud_score=0
    )

    # 3. Shop 2 (FashionHub)
    shop2_user = User(
        email="shop2@fashionhub.vn",
        password_hash=hash_password("Password123!"),
        full_name="Trần Thị Shop (FashionHub)",
        phone="0902222222",
        role=UserRole.SHOP,
        fraud_score=0
    )

    # 4. Shipper
    shipper = User(
        email="shipper@fastship.vn",
        password_hash=hash_password("Password123!"),
        full_name="Lê Văn Shipper (FastShip)",
        phone="0987654321",
        role=UserRole.SHIPPER,
        fraud_score=0
    )

    # 5. Buyer
    buyer = User(
        email="buyer@customer.vn",
        password_hash=hash_password("Password123!"),
        full_name="Phạm Thị Khách Hàng (VIP Buyer)",
        phone="0912345678",
        role=UserRole.BUYER,
        fraud_score=0
    )

    db.add_all([admin, shop1_user, shop2_user, shipper, buyer])
    db.commit()

    print(">>> Seeding Shops...")
    shop1 = Shop(
        owner_id=shop1_user.id,
        shop_name="TechStore Official Hà Nội",
        address="Số 123 Đường Cầu Giấy, Phường Quan Hoa, Quận Cầu Giấy, Hà Nội",
        latitude=21.0333,
        longitude=105.7997,
        commission_rate=0.05,
        wallet_balance=500000.0,
        shop_secret=secrets.token_hex(32)
    )

    shop2 = Shop(
        owner_id=shop2_user.id,
        shop_name="FashionHub Lifestyle Sài Gòn",
        address="Số 88 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
        latitude=10.7769,
        longitude=106.7009,
        commission_rate=0.04,
        wallet_balance=1200000.0,
        shop_secret=secrets.token_hex(32)
    )

    db.add_all([shop1, shop2])
    db.commit()

    print(">>> Seeding Products...")
    p1 = Product(
        shop_id=shop1.id,
        name="Tai nghe Bluetooth Chống Ồn Cao Cấp Sony WH-1000XM5",
        description="Tai nghe chụp tai chống ồn hàng đầu với chip xử lý V1, âm thanh Hi-Res Audio, đàm thoại chuẩn mực.",
        price=6990000.0,
        stock_quantity=15,
        category="Điện Tử",
        images="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop"
    )

    p2 = Product(
        shop_id=shop1.id,
        name="Bàn phím cơ không dây Keychron K2 Pro QMK/VIA",
        description="Bàn phím cơ Layout 75% gọn gàng, switch cơ học gõ êm, kết nối đa thiết bị Bluetooth 5.1 và Type-C.",
        price=2250000.0,
        stock_quantity=20,
        category="Điện Tử",
        images="https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&auto=format&fit=crop"
    )

    p3 = Product(
        shop_id=shop1.id,
        name="Chuột công thái học không dây Logitech MX Master 3S",
        description="Cuộn siêu tốc MagSpeed 1000 dòng/giây, click êm giảm 90% tiếng ồn, cảm biến Darkfield 8000 DPI.",
        price=1890000.0,
        stock_quantity=25,
        category="Điện Tử",
        images="https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=500&auto=format&fit=crop"
    )

    p4 = Product(
        shop_id=shop2.id,
        name="Áo Polo Nam Nano Thoáng Khí Chống Nhăn",
        description="Chất liệu Nano pha Spandex co giãn 4 chiều, thấm hút mồ hôi tối đa, lịch lãm phong cách doanh nhân trẻ.",
        price=350000.0,
        stock_quantity=50,
        category="Thời Trang",
        images="https://images.unsplash.com/photo-1625910513413-5bb1a4b86869?w=500&auto=format&fit=crop"
    )

    p5 = Product(
        shop_id=shop2.id,
        name="Balo Laptop Chống Trộm WaterProof 15.6 inch",
        description="Khóa mã số TSA chống trộm, cổng sạc USB tích hợp bên hông, vải Oxford chống thấm nước chuyên dụng.",
        price=480000.0,
        stock_quantity=30,
        category="Thời Trang",
        images="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&auto=format&fit=crop"
    )

    db.add_all([p1, p2, p3, p4, p5])
    db.commit()

    print(">>> Creating Pre-Packaged Order #1 (PACKED, Ready for Shipper Handshake 1)...")
    order1 = Order(
        buyer_id=buyer.id,
        shop_id=shop1.id,
        total_amount=1890000.0,
        shipping_fee=25000.0,
        final_amount=1915000.0,
        status=OrderStatus.PACKED,
        shipping_address="Số 45 Ngõ 123 Đường Cầu Giấy, Phường Dịch Vọng, Quận Cầu Giấy, Hà Nội",
        buyer_latitude=21.0360,
        buyer_longitude=105.7950,
        masked_phone="091****678",
        payment_method=PaymentMethod.WALLET_ESCROW,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    )
    db.add(order1)
    db.flush()

    item1 = OrderItem(
        order_id=order1.id,
        product_id=p3.id,
        shop_id=shop1.id,
        quantity=1,
        unit_price=1890000.0
    )
    db.add(item1)

    # Package for Order 1 with HMAC Anti-Tamper QR
    token_str1, salt1, sig1, qr_b64_1 = generate_package_token(order1.id, shop1.id, shop1.shop_secret)
    pkg1 = Package(
        order_id=order1.id,
        shop_id=shop1.id,
        shipper_id=None,
        package_token_hash=sig1,
        salt=salt1,
        qr_code_data=token_str1,
        qr_image_base64=qr_b64_1,
        status=PackageStatus.CREATED,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    )
    db.add(pkg1)

    escrow1 = EscrowWallet(
        order_id=order1.id,
        buyer_id=buyer.id,
        shop_id=shop1.id,
        amount=order1.final_amount,
        commission_fee=round(order1.final_amount * shop1.commission_rate, 2),
        net_payout=round(order1.final_amount * (1 - shop1.commission_rate), 2),
        status=EscrowStatus.HELD
    )
    db.add(escrow1)

    print(">>> Creating Pre-Packaged Order #2 (IN_TRANSIT, Ready for Buyer Handshake 2 Verification)...")
    order2 = Order(
        buyer_id=buyer.id,
        shop_id=shop1.id,
        total_amount=2250000.0,
        shipping_fee=20000.0,
        final_amount=2270000.0,
        status=OrderStatus.IN_TRANSIT,
        shipping_address="Số 45 Ngõ 123 Đường Cầu Giấy, Phường Dịch Vọng, Quận Cầu Giấy, Hà Nội",
        buyer_latitude=21.0360,
        buyer_longitude=105.7950,
        masked_phone="091****678",
        payment_method=PaymentMethod.VNPAY_ESCROW,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
    )
    db.add(order2)
    db.flush()

    item2 = OrderItem(
        order_id=order2.id,
        product_id=p2.id,
        shop_id=shop1.id,
        quantity=1,
        unit_price=2250000.0
    )
    db.add(item2)

    token_str2, salt2, sig2, qr_b64_2 = generate_package_token(order2.id, shop1.id, shop1.shop_secret)
    pkg2 = Package(
        order_id=order2.id,
        shop_id=shop1.id,
        shipper_id=shipper.id,
        package_token_hash=sig2,
        salt=salt2,
        qr_code_data=token_str2,
        qr_image_base64=qr_b64_2,
        status=PackageStatus.PICKED_UP,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=4)
    )
    db.add(pkg2)

    escrow2 = EscrowWallet(
        order_id=order2.id,
        buyer_id=buyer.id,
        shop_id=shop1.id,
        amount=order2.final_amount,
        commission_fee=round(order2.final_amount * shop1.commission_rate, 2),
        net_payout=round(order2.final_amount * (1 - shop1.commission_rate), 2),
        status=EscrowStatus.HELD
    )
    db.add(escrow2)

    # Initial Audit Logs
    audit1 = AuditLog(
        event_type="TOKEN_GENERATED",
        order_id=order1.id,
        package_id=pkg1.id,
        user_id=shop1_user.id,
        details="Generated anti-tamper QR packaging token for Order #1"
    )
    audit2 = AuditLog(
        event_type="HANDSHAKE_PICKUP",
        order_id=order2.id,
        package_id=pkg2.id,
        user_id=shipper.id,
        details=f"Shipper {shipper.full_name} picked up Package for Order #2 from TechStore warehouse"
    )
    db.add_all([audit1, audit2])

    db.commit()
    db.close()
    print("=================================================================")
    print(" Seed Data Created Successfully!")
    print(" Test Accounts:")
    print("   1. Admin:   admin@ecommerce.vn   / Password123!")
    print("   2. Shop:    shop1@techstore.vn   / Password123!")
    print("   3. Shop 2:  shop2@fashionhub.vn  / Password123!")
    print("   4. Shipper: shipper@fastship.vn  / Password123!")
    print("   5. Buyer:   buyer@customer.vn    / Password123!")
    print("=================================================================")

if __name__ == "__main__":
    seed()
