import pytest
import asyncio
from fastapi.testclient import TestClient
import uuid
import sys
import os

# Append backend to path so we can import the api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from api.models.database import Base, UserRole
from sqlalchemy.ext.asyncio import create_async_engine

# Use an in-memory SQLite DB specifically for fast unit testing decoupled from dev state
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    return create_async_engine(TEST_DB_URL, echo=False)

@pytest.fixture(autouse=True)
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

# The client can't trivially override the get_db dependency for everything without complex mocking, 
# so we will test the exact FastAPI app behavior ignoring DB state for pure syntax. 
# Oh wait, we CAN override dependencies in FastAPI easily!
from api.deps import get_db
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

async def override_get_db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_user_registration():
    response = client.post("/auth/register", json={
        "full_name": "Test User",
        "email": "test@unit.edu",
        "password": "valid_password",
        "institution": "Test University",
        "role": "student"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@unit.edu"
    assert data["user"]["role"] == "student"

def test_duplicate_user_registration():
    # Attempt to register the exact same user again
    response = client.post("/auth/register", json={
        "full_name": "Test User",
        "email": "test@unit.edu",
        "password": "valid_password",
        "institution": "Test University",
        "role": "student"
    })
    # Must fail with 400 Bad Request
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()

def test_user_login_valid_credentials():
    # Using the user created in test_user_registration
    response = client.post("/auth/login", json={
        "email": "test@unit.edu",
        "password": "valid_password"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@unit.edu"

def test_user_login_invalid_password():
    response = client.post("/auth/login", json={
        "email": "test@unit.edu",
        "password": "wrong_password"
    })
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()

def test_protected_route_without_token():
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_protected_route_with_token():
    # Login to get token first
    login_response = client.post("/auth/login", json={
        "email": "test@unit.edu",
        "password": "valid_password"
    })
    token = login_response.json()["access_token"]

    # Now request /auth/me with Bearer token
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "test@unit.edu"

def test_create_survey():
    # Login
    token = client.post("/auth/login", json={"email": "test@unit.edu", "password": "valid_password"}).json()["access_token"]
    
    response = client.post("/surveys", 
        json={"title": "My Unit Test Survey", "description": "Testing the survey creation"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My Unit Test Survey"
    assert data["status"] == "draft"
    assert data["user_id"] is not None

def test_get_surveys_list():
    token = client.post("/auth/login", json={"email": "test@unit.edu", "password": "valid_password"}).json()["access_token"]
    response = client.get("/surveys", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    # Must be minimum 1 because test_create_survey just created one
    assert len(response.json()) >= 1
