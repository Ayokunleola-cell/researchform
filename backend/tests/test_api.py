"""
Backend API test suite.

Auth flow: register → verify OTP (reads OTP from shared test DB) → get token
"""
import pytest
import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from api.models.database import Base
from api.deps import get_db

# ── Shared in-file DB (same engine for all tests) ──────────────────────────
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), 'test_run.db')
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# Single shared engine + session factory reused across all test requests
_engine = create_async_engine(TEST_DB_URL, echo=False,
                              connect_args={"check_same_thread": False, "timeout": 30})
_AsyncSessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _create_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    """Dependency override that uses the shared test engine."""
    async with _AsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    """Create tables once for the whole test session."""
    asyncio.run(_create_tables())
    yield
    asyncio.run(_drop_tables())
    # Remove file-based test DB after session
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


# ── Helpers ─────────────────────────────────────────────────────────────────

def _read_otp(email: str, purpose: str) -> str | None:
    """Read the latest valid OTP from the shared test DB."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker as sm
    from api.models.database import User, UserOTP

    async def _fetch():
        eng = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = sm(eng, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as s:
            r = await s.execute(select(User).where(User.email == email))
            user = r.scalar_one_or_none()
            if not user:
                return None
            r2 = await s.execute(
                select(UserOTP)
                .where(UserOTP.user_id == user.id, UserOTP.purpose == purpose)
                .order_by(UserOTP.expires_at.desc())
            )
            otp = r2.scalars().first()
            return otp.otp_code if otp else None

    return asyncio.run(_fetch())


def register_and_verify(email: str, password: str = "ValidPass123!") -> str:
    """Full registration flow → returns access_token."""
    r = client.post("/auth/register", json={
        "full_name": "Test User",
        "email": email,
        "password": password,
        "institution": "Test University",
        "role": "student",
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    assert r.json()["status"] == "pending_verification"

    otp = _read_otp(email, "register")
    assert otp, f"OTP not found for {email}"

    v = client.post("/auth/verify-otp", json={"email": email, "otp_code": otp, "purpose": "register"})
    assert v.status_code == 200, f"OTP verify failed: {v.text}"
    return v.json()["access_token"]


def login_and_verify(email: str, password: str = "ValidPass123!") -> str:
    """Full login flow → returns access_token."""
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    assert r.json().get("status") == "pending_verification"

    otp = _read_otp(email, "login")
    assert otp, f"Login OTP not found for {email}"

    v = client.post("/auth/verify-otp", json={"email": email, "otp_code": otp, "purpose": "login"})
    assert v.status_code == 200, f"Login OTP verify failed: {v.text}"
    return v.json()["access_token"]


# ── Tests ────────────────────────────────────────────────────────────────────

def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_user_registration():
    email = f"reg_{uuid.uuid4().hex[:6]}@unit.edu"
    token = register_and_verify(email)
    assert token and len(token) > 10


def test_duplicate_user_registration():
    email = f"dup_{uuid.uuid4().hex[:6]}@unit.edu"
    register_and_verify(email)
    # Re-registering a verified user must return 400
    r = client.post("/auth/register", json={
        "full_name": "Test User", "email": email,
        "password": "ValidPass123!", "institution": "Test University", "role": "student",
    })
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"].lower()


def test_login_valid_credentials():
    email = f"login_{uuid.uuid4().hex[:6]}@unit.edu"
    register_and_verify(email)
    token = login_and_verify(email)
    assert token and len(token) > 10


def test_login_invalid_password():
    email = f"badpw_{uuid.uuid4().hex[:6]}@unit.edu"
    register_and_verify(email)
    r = client.post("/auth/login", json={"email": email, "password": "WrongPassword!"})
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


def test_protected_route_without_token():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_protected_route_with_token():
    email = f"prot_{uuid.uuid4().hex[:6]}@unit.edu"
    token = register_and_verify(email)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_create_survey():
    email = f"surv_{uuid.uuid4().hex[:6]}@unit.edu"
    token = register_and_verify(email)
    r = client.post(
        "/surveys",
        json={"title": "My Unit Test Survey", "description": "Testing survey creation"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "My Unit Test Survey"
    assert data["status"] == "draft"
    assert data["user_id"] is not None


def test_get_surveys_list():
    email = f"list_{uuid.uuid4().hex[:6]}@unit.edu"
    token = register_and_verify(email)
    # Create one survey first
    client.post("/surveys",
        json={"title": "List Test Survey"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.get("/surveys", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_credits_wallet_requires_auth():
    r = client.get("/credits/wallet")
    assert r.status_code == 401


def test_credits_wallet_with_auth():
    email = f"cred_{uuid.uuid4().hex[:6]}@unit.edu"
    token = register_and_verify(email)
    r = client.get("/credits/wallet", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "balance" in r.json()
