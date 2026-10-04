"""
Module 1 - Authorization (RBAC) test suite.

Proves that a Buyer cannot invoke Admin/Shop/Shipper endpoints (and vice-versa),
that unauthenticated callers get 401, and that each role can still use its own
allowed endpoints.
"""
import pytest

from app.models import UserRole

# (method, path, json_body) triples. Bodies are valid so that a forbidden role
# fails with 403 (RBAC) rather than 422 (body validation).
ADMIN_ONLY = [
    ("GET", "/api/admin/metrics", None),
    ("GET", "/api/admin/audit-logs", None),
    ("GET", "/api/admin/flagged-users", None),
    ("POST", "/api/admin/users/1/reset-fraud-score", None),
    ("POST", "/api/disputes/1/resolve", {"status": "RESOLVED", "action": "REFUND_BUYER"}),
    ("POST", "/api/escrow/order/1/release", None),
    ("POST", "/api/escrow/order/1/refund", None),
]

SHOP_ENDPOINTS = [
    ("GET", "/api/shop/orders", None),
    ("GET", "/api/shop/profile", None),
    ("POST", "/api/shop/products", {"name": "P", "price": 1000, "stock_quantity": 1, "category": "C"}),
    ("POST", "/api/shop/orders/1/pack", None),
]

SHIPPER_ENDPOINTS = [
    ("GET", "/api/shipper/available-packages", None),
    ("POST", "/api/shipper/handshake-pickup", {"qr_token": "x"}),
]

BUYER_ONLY = [
    ("POST", "/api/buyer/verify-package", {"qr_token": "x"}),
    ("POST", "/api/orders/checkout", {"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "a", "phone": "1"}),
    ("POST", "/api/reviews", {"product_id": 1, "order_id": 1, "rating": 5}),
]


def _call(client, method, path, headers, body):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


@pytest.fixture(autouse=True)
def _create_rbac_users(make_user):
    make_user("admin@test.vn", role=UserRole.ADMIN)
    make_user("shop@test.vn", role=UserRole.SHOP)
    make_user("shipper@test.vn", role=UserRole.SHIPPER)
    make_user("buyer@test.vn", role=UserRole.BUYER)


EMAILS = {
    "Admin": "admin@test.vn",
    "Shop": "shop@test.vn",
    "Shipper": "shipper@test.vn",
    "Buyer": "buyer@test.vn",
}


def _forbidden_cases():
    cases = []
    # Buyer must NOT reach Admin, Shop or Shipper endpoints.
    for method, path, body in ADMIN_ONLY + SHOP_ENDPOINTS + SHIPPER_ENDPOINTS:
        cases.append(("Buyer", method, path, body))
    # Shop must NOT reach Admin, Buyer or Shipper endpoints.
    for method, path, body in ADMIN_ONLY + BUYER_ONLY + SHIPPER_ENDPOINTS:
        cases.append(("Shop", method, path, body))
    # Shipper must NOT reach Admin, Shop or Buyer endpoints.
    for method, path, body in ADMIN_ONLY + SHOP_ENDPOINTS + BUYER_ONLY:
        cases.append(("Shipper", method, path, body))
    return cases


@pytest.mark.parametrize("role,method,path,body", _forbidden_cases())
def test_forbidden_roles_are_denied(client, headers_for, role, method, path, body):
    headers = headers_for(EMAILS[role])
    res = _call(client, method, path, headers, body)
    assert res.status_code == 403, f"{role} unexpectedly reached {method} {path} -> {res.status_code}: {res.text}"


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY + SHOP_ENDPOINTS + SHIPPER_ENDPOINTS + BUYER_ONLY)
def test_unauthenticated_requests_get_401(client, method, path, body):
    res = _call(client, method, path, headers=None, body=body)
    assert res.status_code == 401, f"Unauthenticated {method} {path} -> {res.status_code}: {res.text}"


def test_admin_can_reach_admin_endpoints(client, headers_for):
    headers = headers_for(EMAILS[UserRole.ADMIN])
    assert client.get("/api/admin/metrics", headers=headers).status_code == 200
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 200
    assert client.get("/api/admin/flagged-users", headers=headers).status_code == 200


def test_shop_can_reach_own_endpoints(client, headers_for):
    headers = headers_for(EMAILS[UserRole.SHOP])
    assert client.get("/api/shop/profile", headers=headers).status_code == 200
    assert client.get("/api/shop/orders", headers=headers).status_code == 200


def test_buyer_can_reach_own_endpoints(client, headers_for):
    headers = headers_for(EMAILS[UserRole.BUYER])
    assert client.get("/api/buyer/orders", headers=headers).status_code == 200


def test_shipper_can_reach_own_endpoints(client, headers_for):
    headers = headers_for(EMAILS[UserRole.SHIPPER])
    assert client.get("/api/shipper/available-packages", headers=headers).status_code == 200


def test_invalid_token_is_rejected(client):
    res = client.get("/api/admin/metrics", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_buyer_cannot_cross_into_shop_by_url_guessing(client, headers_for):
    """Explicit regression guard for the assignment requirement."""
    headers = headers_for(EMAILS[UserRole.BUYER])
    assert client.get("/api/shop/orders", headers=headers).status_code == 403
    assert client.post(
        "/api/shop/products",
        json={"name": "hack", "price": 1, "stock_quantity": 1, "category": "x"},
        headers=headers,
    ).status_code == 403
    assert client.get("/api/admin/metrics", headers=headers).status_code == 403
