"""
Shared pytest fixtures.

The application reads configuration at import time, so the isolated test
database and deterministic security settings are injected into the environment
*before* ``app.main`` is imported.
"""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Isolated throwaway database + deterministic config (before app import) ---
_db_fd, _db_path = tempfile.mkstemp(prefix="btl_auth_test_", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "pytest-secret-key-do-not-use-in-prod"
os.environ["ENVIRONMENT"] = "test"
os.environ["CAPTCHA_ENABLED"] = "false"
os.environ["EXPOSE_RESET_TOKEN"] = "true"
os.environ["ACCOUNT_MAX_FAILED_ATTEMPTS"] = "5"
os.environ["ACCOUNT_LOCKOUT_MINUTES"] = "15"
os.environ["LOGIN_RATE_LIMIT_MAX"] = "50"
os.environ["PASSWORD_RESET_RATE_LIMIT_MAX"] = "50"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.modules.auth import notifications, rate_limit  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state():
    """Fresh schema + limiter state for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit.reset_all()
    notifications.reset_outbox()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(_reset_state):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_reset_state):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(db):
    def _make(email, password="Password123!", role=UserRole.BUYER, **kwargs):
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=kwargs.get("full_name", f"Test {role}"),
            phone=kwargs.get("phone"),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def token_for(client):
    def _token(email, password="Password123!"):
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return res.json()["access_token"]

    return _token


@pytest.fixture
def headers_for(token_for):
    def _headers(email, password="Password123!"):
        return {"Authorization": f"Bearer {token_for(email, password)}"}

    return _headers
