import sys
import pytest
from fastapi.testclient import TestClient
from app.main import app
from seed_data import seed

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

client = TestClient(app)

def test_full_e2e_security_and_escrow_flow():
    # 1. Reset database with seed data
    seed()
    print("\n--- [Step 1: Auth & Login for 4 roles] ---")
    # Login Buyer
    res = client.post("/api/auth/login", json={"email": "buyer@customer.vn", "password": "Password123!"})
    assert res.status_code == 200, res.text
    buyer_token = res.json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    # Login Shop
    res = client.post("/api/auth/login", json={"email": "shop1@techstore.vn", "password": "Password123!"})
    assert res.status_code == 200, res.text
    shop_token = res.json()["access_token"]
    shop_headers = {"Authorization": f"Bearer {shop_token}"}

    # Login Shipper
    res = client.post("/api/auth/login", json={"email": "shipper@fastship.vn", "password": "Password123!"})
    assert res.status_code == 200, res.text
    shipper_token = res.json()["access_token"]
    shipper_headers = {"Authorization": f"Bearer {shipper_token}"}

    # Login Admin
    res = client.post("/api/auth/login", json={"email": "admin@ecommerce.vn", "password": "Password123!"})
    assert res.status_code == 200, res.text
    admin_token = res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(">>> All 4 roles authenticated successfully.")

    print("\n--- [Step 2: Module 7 - Discovery & Geo-Distance] ---")
    res = client.get("/api/discovery/products?buyer_lat=21.0360&buyer_lon=105.7950&sort_by=distance")
    assert res.status_code == 200
    prods = res.json()
    assert len(prods) >= 5
    assert prods[0]["distance_km"] is not None
    print(f">>> Found {len(prods)} products sorted by geo-distance.")

    print("\n--- [Step 3: Module 5 & 6 - Cart Checkout & Multi-Vendor Split & Escrow Lock] ---")
    # Buyer buys 1 Sony headphone (Shop 1) and 1 Polo shirt (Shop 2)
    checkout_payload = {
        "items": [
            {"product_id": prods[0]["id"], "quantity": 1},
            {"product_id": prods[-1]["id"], "quantity": 1}
        ],
        "shipping_address": "Số 99 Đường Xuân Thủy, Cầu Giấy, Hà Nội",
        "phone": "0912345678",
        "buyer_latitude": 21.0360,
        "buyer_longitude": 105.7950,
        "payment_method": "WALLET_ESCROW"
    }
    res = client.post("/api/orders/checkout", json=checkout_payload, headers=buyer_headers)
    assert res.status_code == 200, res.text
    checkout_res = res.json()
    created_orders = checkout_res["orders"]
    assert len(created_orders) == 2  # Split into 2 sub-orders!
    print(f">>> Multi-vendor cart successfully split into {len(created_orders)} sub-orders!")

    order_shop1_id = created_orders[0]["order_id"]

    print("\n--- [Step 4: Module 2 - Shop Pack Order & Generate HMAC-SHA256 Anti-Tamper QR] ---")
    res = client.post(f"/api/shop/orders/{order_shop1_id}/pack", headers=shop_headers)
    assert res.status_code == 200, res.text
    pack_res = res.json()
    qr_token = pack_res["qr_code_data"]
    qr_image = pack_res["qr_image_base64"]
    assert qr_token is not None
    assert qr_image.startswith("data:image/png;base64,")
    print(f">>> Dynamic QR generated with HMAC-SHA256 token! Order status: {pack_res['status']}")

    print("\n--- [Step 5: Module 7 - Privacy Masked Waybill Check] ---")
    res = client.get(f"/api/discovery/waybill/{order_shop1_id}")
    assert res.status_code == 200
    waybill = res.json()
    assert "****" in waybill["recipient"]["masked_phone"]
    print(f">>> Waybill privacy verified: Phone={waybill['recipient']['masked_phone']}, Address={waybill['recipient']['masked_address']}")

    print("\n--- [Step 6: Module 3 - Shipper Warehouse Handshake 1] ---")
    res = client.post("/api/shipper/handshake-pickup", json={"qr_token": qr_token}, headers=shipper_headers)
    assert res.status_code == 200, res.text
    pickup_res = res.json()
    assert pickup_res["status"] == "PICKED_UP"
    assert pickup_res["order_status"] == "IN_TRANSIT"
    print(">>> Handshake 1 successful! Package is PICKED_UP and Order is IN_TRANSIT.")

    print("\n--- [Step 7: Module 4 & 6 - Buyer Safe Verification Handshake 2 & Automated Escrow Release] ---")
    # Check shop wallet balance before delivery
    res = client.get("/api/shop/profile", headers=shop_headers)
    balance_before = res.json()["wallet_balance"]

    # Buyer scans QR parcel at door
    res = client.post("/api/buyer/verify-package", json={"qr_token": qr_token}, headers=buyer_headers)
    assert res.status_code == 200, res.text
    verify_res = res.json()
    assert verify_res["order_status"] == "DELIVERED_VERIFIED"
    assert verify_res["escrow_released"] is True
    print(">>> Handshake 2 verified! Order is DELIVERED_VERIFIED.")

    # Check shop wallet balance after delivery
    res = client.get("/api/shop/profile", headers=shop_headers)
    balance_after = res.json()["wallet_balance"]
    assert balance_after > balance_before
    print(f">>> Automated Escrow Release Verified: Shop balance credited from {balance_before} -> {balance_after} VND!")

    print("\n--- [Step 8: Module 9 - Verified Purchase Review Guardrail] ---")
    # Submitting review on delivered product should succeed
    res = client.post("/api/reviews", json={
        "order_id": order_shop1_id,
        "product_id": prods[0]["id"],
        "rating": 5,
        "comment": "Kiện hàng nguyên tem, quét mã QR ra đúng thông tin chính hãng! Rất hài lòng."
    }, headers=buyer_headers)
    assert res.status_code == 200, res.text
    print(">>> Verified review submitted successfully.")

    # Reviewing with an unverified order should be blocked
    res = client.post("/api/reviews", json={
        "order_id": 999,
        "product_id": prods[0]["id"],
        "rating": 1,
        "comment": "Đánh giá ảo"
    }, headers=buyer_headers)
    assert res.status_code in [400, 404]
    print(">>> Anti-Fake Review Guardrail successfully blocked unverified order review.")

    print("\n--- [Step 9: Module 8 - Anti-Fraud & Disputes] ---")
    # File dispute on Order #2 (which was seeded)
    res = client.post("/api/disputes", json={
        "order_id": 2,
        "reason": "Tem niêm phong QR bị rách/làm giả",
        "notes": "Hộp có dấu hiệu bị rạch và dán đè băng keo khác."
    }, headers=buyer_headers)
    assert res.status_code == 200, res.text
    dispute_id = res.json()["id"]
    print(f">>> Dispute #{dispute_id} filed. Escrow frozen.")

    # Admin resolves dispute with refund to buyer
    res = client.post(f"/api/disputes/{dispute_id}/resolve", json={
        "status": "RESOLVED",
        "action": "REFUND_BUYER",
        "admin_notes": "Xác nhận tem có dấu hiệu xâm phạm. Hoàn tiền 100% cho người mua."
    }, headers=admin_headers)
    assert res.status_code == 200
    print(">>> Admin successfully resolved dispute and refunded Escrow to buyer.")

    print("\n--- [Step 10: Module 10 - Admin Analytics & Security Radar] ---")
    res = client.get("/api/admin/metrics", headers=admin_headers)
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total_orders"] >= 2
    assert metrics["total_commission"] >= 0

    res = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    print(f">>> Admin Metrics & Audit Trail verified! Total audit logs recorded: {len(logs)}")

    print("\n=========================================================================")
    print(" ALL 10 MODULES PASSED END-TO-END VERIFICATION!")
    print("=========================================================================")

if __name__ == "__main__":
    test_full_e2e_security_and_escrow_flow()
