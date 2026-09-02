import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient
import sys
import os
import uuid
from datetime import datetime, timedelta
from jose import jwt

# Append backend to path so we can import the api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from api.models.database import Base, User
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from api.deps import get_db
from config import settings
from api.routers.auth import make_token

TEST_DB_URL = "sqlite+aiosqlite:///./test_integration.db"
DATANEST_URL = "http://localhost:8001/api/market"

@pytest.fixture(scope="module")
def engine():
    return create_async_engine(TEST_DB_URL, echo=False)

@pytest.fixture(autouse=True, scope="module")
def setup_db(engine):
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_setup())
    yield
    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.run(_teardown())

async def override_get_db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ---------------------------------------------------------
# Unit Tests: JWT Logic
# ---------------------------------------------------------
def test_jwt_payload_has_required_claims():
    """Verify that ResearchForm generates JWTs compatible with DataNest auto-provisioning."""
    fake_user = User(
        id="test-user-" + str(uuid.uuid4()),
        email="test_integration@example.com",
        full_name="Integration Tester",
        role="researcher"
    )
    
    token = make_token(fake_user)
    
    # Decode token ignoring signature for inspection
    payload = jwt.get_unverified_claims(token)
    
    assert "sub" in payload, "Token missing 'sub' claim"
    assert "email" in payload, "Token missing 'email' claim"
    assert "name" in payload, "Token missing 'name' claim"
    assert "exp" in payload, "Token missing 'exp' claim"
    
    assert payload["sub"] == fake_user.id
    assert payload["email"] == fake_user.email
    assert payload["name"] == fake_user.full_name

def test_jwt_expiration():
    """Verify that ResearchForm JWT tokens expire in the future."""
    fake_user = User(
        id="test-user-" + str(uuid.uuid4()),
        email="test_integration2@example.com",
        full_name="Integration Tester 2"
    )
    token = make_token(fake_user)
    payload = jwt.get_unverified_claims(token)
    
    exp = datetime.utcfromtimestamp(payload["exp"])
    assert exp > datetime.utcnow(), "Token expiration is in the past"

# ---------------------------------------------------------
# Integration Tests: DataNest Cross-Server Communication
# ---------------------------------------------------------
@pytest.fixture(scope="module")
def rf_token():
    """Register and login a test user in ResearchForm to get a real token."""
    email = f"datanest_test_{uuid.uuid4()}@example.com"
    reg_res = client.post("/auth/register", json={
        "full_name": "DataNest Cross-Server Tester",
        "email": email,
        "password": "strong_password123",
        "institution": "Test Inst",
        "role": "researcher"
    })
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    
    login_res = client.post("/auth/login", json={
        "email": email,
        "password": "strong_password123"
    })
    
    assert login_res.status_code == 200, "Failed to login to ResearchForm for test setup"
    return login_res.json()["access_token"]

def test_datanest_public_endpoints():
    """Verify DataNest public endpoints are reachable."""
    res = httpx.get(f"{DATANEST_URL}/featured")
    # Even if empty, it should be 200 OK
    assert res.status_code == 200, f"Featured endpoint returned {res.status_code}"
    
    res = httpx.get(f"{DATANEST_URL}/datasets")
    assert res.status_code == 200, f"Datasets list endpoint returned {res.status_code}"
    assert "items" in res.json(), "Invalid paginated response format"

def test_datanest_auto_provisioning(rf_token):
    """
    Test the critical integration path:
    Send ResearchForm token to DataNest.
    DataNest should successfully decode it and auto-create the user.
    """
    headers = {"Authorization": f"Bearer {rf_token}"}
    
    # /me/library requires an authenticated user
    res = httpx.get(f"{DATANEST_URL}/me/library", headers=headers)
    
    assert res.status_code == 200, f"Auto-provisioning failed. Expected 200, got {res.status_code}: {res.text}"
    assert isinstance(res.json(), list), "Library endpoint should return a list"

def test_datanest_protected_endpoints(rf_token):
    """Test DataNest seller analytics with ResearchForm token."""
    headers = {"Authorization": f"Bearer {rf_token}"}
    
    res = httpx.get(f"{DATANEST_URL}/sell/analytics", headers=headers)
    assert res.status_code == 200, f"Failed to fetch seller analytics: {res.text}"
    data = res.json()
    assert "total_sales" in data
    assert "total_downloads" in data
