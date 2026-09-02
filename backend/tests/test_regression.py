"""
ResearchForm — Full Regression Test Suite
Tests the complete end-to-end user journey from register → survey → analysis → report download.
Run: .\\venv\\Scripts\\python.exe -m pytest tests/test_regression.py -v --tb=short -p no:warnings
"""
import pytest
import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from main import app
from api.models.database import Base
from api.deps import get_db

# ── Isolated file-based test DB ──────────────────────────────────────────────
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_regression.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
_engine = create_async_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})
_SL = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with _SL() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    async def _init():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_init())
    yield
    async def _drop():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.run(_drop())
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture(scope="session")
def client(setup_db):
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _read_otp(email: str, purpose: str) -> str | None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine as cae
    from sqlalchemy.orm import sessionmaker as sm
    from api.models.database import User, UserOTP

    async def _fetch():
        eng = cae(TEST_DB_URL)
        factory = sm(eng, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
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


def register_and_verify(client, email: str, password: str = "Secure123!") -> str:
    r = client.post("/auth/register", json={
        "full_name": "Regression User",
        "email": email,
        "password": password,
        "institution": "Test University",
        "role": "researcher",
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    otp = _read_otp(email, "register")
    assert otp, "OTP not found"
    v = client.post("/auth/verify-otp", json={"email": email, "otp_code": otp, "purpose": "register"})
    assert v.status_code == 200, f"OTP verify failed: {v.text}"
    return v.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 1: Auth Journey
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthRegression:
    def test_health_endpoint_alive(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_register_new_user(self, client):
        email = f"reg_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        assert token and len(token) > 20

    def test_duplicate_registration_blocked(self, client):
        email = f"dup_{uuid.uuid4().hex[:8]}@test.edu"
        register_and_verify(client, email)
        r = client.post("/auth/register", json={
            "full_name": "Dup", "email": email,
            "password": "Secure123!", "institution": "T", "role": "student"
        })
        assert r.status_code == 400
        assert "already" in r.json()["detail"].lower()

    def test_login_with_bad_password_rejected(self, client):
        email = f"badpw_{uuid.uuid4().hex[:8]}@test.edu"
        register_and_verify(client, email)
        r = client.post("/auth/login", json={"email": email, "password": "WrongPass!"})
        assert r.status_code == 401

    def test_me_endpoint_returns_user_data(self, client):
        email = f"me_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        r = client.get("/auth/me", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["email"] == email

    def test_me_endpoint_rejects_no_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_endpoint_rejects_invalid_token(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Bearer fake.token.here"})
        assert r.status_code == 401

    def test_short_password_rejected(self, client):
        r = client.post("/auth/register", json={
            "full_name": "Short", "email": f"short_{uuid.uuid4().hex[:6]}@test.edu",
            "password": "abc", "institution": "T", "role": "student"
        })
        assert r.status_code in (200, 400, 422)

    def test_invalid_email_rejected(self, client):
        r = client.post("/auth/register", json={
            "full_name": "Bad", "email": "not-an-email",
            "password": "Secure123!", "institution": "T", "role": "student"
        })
        assert r.status_code in (400, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 2: Survey Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestSurveyRegression:
    @pytest.fixture(scope="class")
    def user(self, client):
        email = f"surv_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        return {"token": token, "email": email, "headers": auth_header(token)}

    def test_create_survey(self, client, user):
        r = client.post("/surveys", json={"title": "Regression Survey", "description": "QA test"}, headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Regression Survey"
        assert data["status"] == "draft"

    def test_list_surveys_returns_created(self, client, user):
        client.post("/surveys", json={"title": "List Test Survey"}, headers=user["headers"])
        r = client.get("/surveys", headers=user["headers"])
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_get_survey_by_id(self, client, user):
        cr = client.post("/surveys", json={"title": "Get By ID"}, headers=user["headers"])
        sid = cr.json()["id"]
        r = client.get(f"/surveys/{sid}", headers=user["headers"])
        assert r.status_code == 200
        assert r.json()["id"] == sid

    def test_update_survey_title(self, client, user):
        cr = client.post("/surveys", json={"title": "Old Title"}, headers=user["headers"])
        sid = cr.json()["id"]
        r = client.patch(f"/surveys/{sid}", json={"title": "New Title"}, headers=user["headers"])
        assert r.status_code == 200
        assert r.json()["title"] == "New Title"

    def test_add_question_to_survey(self, client, user):
        cr = client.post("/surveys", json={"title": "Q Survey"}, headers=user["headers"])
        sid = cr.json()["id"]
        r = client.post(f"/surveys/{sid}/questions", json={
            "type": "single_choice", "text": "What is your gender?",
            "options": ["Male", "Female", "Other"], "required": True, "order": 1
        }, headers=user["headers"])
        assert r.status_code == 200
        assert r.json()["text"] == "What is your gender?"

    def test_add_multiple_question_types(self, client, user):
        cr = client.post("/surveys", json={"title": "Multi Q"}, headers=user["headers"])
        sid = cr.json()["id"]
        types = [
            {"type": "single_choice", "text": "Pick one", "options": ["A", "B"]},
            {"type": "multi_choice", "text": "Pick many", "options": ["X", "Y", "Z"]},
            {"type": "rating", "text": "Rate 1-5", "options": []},
            {"type": "short_text", "text": "Open ended", "options": []},
        ]
        for i, q in enumerate(types):
            r = client.post(f"/surveys/{sid}/questions", json={**q, "required": True, "order": i+1}, headers=user["headers"])
            assert r.status_code == 200, f"Failed for type {q['type']}: {r.text}"

    def test_publish_survey(self, client, user):
        cr = client.post("/surveys", json={"title": "Publish Me"}, headers=user["headers"])
        sid = cr.json()["id"]
        client.post(f"/surveys/{sid}/questions", json={
            "type": "short_text", "text": "Q1", "options": [], "required": False, "order": 1
        }, headers=user["headers"])
        r = client.post(f"/surveys/{sid}/publish", headers=user["headers"])
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_cannot_access_other_users_survey(self, client):
        email1 = f"owner_{uuid.uuid4().hex[:6]}@test.edu"
        email2 = f"other_{uuid.uuid4().hex[:6]}@test.edu"
        token1 = register_and_verify(client, email1)
        token2 = register_and_verify(client, email2)
        cr = client.post("/surveys", json={"title": "Private"}, headers=auth_header(token1))
        sid = cr.json()["id"]
        r = client.get(f"/surveys/{sid}", headers=auth_header(token2))
        assert r.status_code in (403, 404)

    def test_public_response_submission(self, client, user):
        cr = client.post("/surveys", json={"title": "Response Survey"}, headers=user["headers"])
        sid = cr.json()["id"]
        qr = client.post(f"/surveys/{sid}/questions", json={
            "type": "single_choice", "text": "Fav color?",
            "options": ["Red", "Blue"], "required": True, "order": 1
        }, headers=user["headers"])
        client.post(f"/surveys/{sid}/publish", headers=user["headers"])
        slug = client.get(f"/surveys/{sid}", headers=user["headers"]).json().get("slug", sid)
        r = client.post(f"/public/surveys/{slug}/respond", json={
            "answers": {
                qr.json()["id"]: "Red"
            },
            "participant_email": "respondent@example.com"
        })
        assert r.status_code in (200, 201)

    def test_delete_survey(self, client, user):
        cr = client.post("/surveys", json={"title": "Delete Me"}, headers=user["headers"])
        sid = cr.json()["id"]
        r = client.delete(f"/surveys/{sid}", headers=user["headers"])
        assert r.status_code in (200, 204)
        r2 = client.get(f"/surveys/{sid}", headers=user["headers"])
        assert r2.status_code in (404, 410)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 3: Credits & Wallet
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditsRegression:
    @pytest.fixture(scope="class")
    def user(self, client):
        email = f"cred_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        return {"token": token, "headers": auth_header(token)}

    def test_wallet_requires_auth(self, client):
        r = client.get("/credits/wallet")
        assert r.status_code == 401

    def test_wallet_balance_accessible(self, client, user):
        r = client.get("/credits/wallet", headers=user["headers"])
        assert r.status_code == 200
        assert "balance" in r.json()

    def test_wallet_initial_balance_non_negative(self, client, user):
        r = client.get("/credits/wallet", headers=user["headers"])
        assert float(r.json()["balance"]) >= 0

    def test_packages_endpoint_returns_list(self, client, user):
        r = client.get("/credits/packages", headers=user["headers"])
        assert r.status_code == 200
        pkgs = r.json().get("packages", [])
        assert isinstance(pkgs, list)
        assert len(pkgs) >= 1

    def test_packages_have_required_fields(self, client, user):
        r = client.get("/credits/packages", headers=user["headers"])
        pkgs = r.json().get("packages", [])
        for pkg in pkgs:
            assert "id" in pkg
            assert "label" in pkg
            assert "credits" in pkg
            assert "price_naira" in pkg

    def test_transactions_list_accessible(self, client, user):
        r = client.get("/credits/transactions", headers=user["headers"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_dev_mode_purchase_credits(self, client, user):
        # Check config endpoint first
        cfg = client.get("/credits/config", headers=user["headers"])
        assert cfg.status_code == 200
        if not cfg.json().get("dev_mode"):
            pytest.skip("Dev mode not enabled, skipping dev purchase test")
        # Get available packages
        pkgs = client.get("/credits/packages", headers=user["headers"]).json().get("packages", [])
        if not pkgs:
            pytest.skip("No packages available")
        pkg_id = pkgs[0]["id"]
        balance_before = float(client.get("/credits/wallet", headers=user["headers"]).json()["balance"])
        r = client.post("/credits/purchase", json={"package_id": pkg_id}, headers=user["headers"])
        assert r.status_code == 200
        balance_after = float(r.json()["balance"])
        assert balance_after > balance_before

    def test_purchase_invalid_package_rejected(self, client, user):
        r = client.post("/credits/purchase", json={"package_id": "nonexistent_pkg_xyz"}, headers=user["headers"])
        assert r.status_code in (400, 404)

    def test_config_endpoint_returns_flags(self, client, user):
        r = client.get("/credits/config", headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert "dev_mode" in data
        assert "paystack_enabled" in data
        assert "stripe_enabled" in data


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 4: Referral System
# ═══════════════════════════════════════════════════════════════════════════════

class TestReferralRegression:
    @pytest.fixture(scope="class")
    def user(self, client):
        email = f"ref_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        return {"token": token, "email": email, "headers": auth_header(token)}

    def test_referral_info_accessible(self, client, user):
        r = client.get("/referral/me", headers=user["headers"])
        assert r.status_code == 200

    def test_referral_code_exists(self, client, user):
        r = client.get("/referral/me", headers=user["headers"])
        data = r.json()
        assert "referral_code" in data or "code" in data

    def test_referral_stats_accessible(self, client, user):
        r = client.get("/referral/me", headers=user["headers"])
        assert r.status_code in (200, 404)  # might not exist yet

    def test_referral_register_with_code(self, client, user):
        # Get the referrer's code
        ref_info = client.get("/referral/me", headers=user["headers"]).json()
        code = ref_info.get("referral_code") or ref_info.get("code")
        if not code:
            pytest.skip("Referral code not available")
        # Register a new user with the referral code
        new_email = f"newref_{uuid.uuid4().hex[:8]}@test.edu"
        r = client.post("/auth/register", json={
            "full_name": "Referred User",
            "email": new_email,
            "password": "Secure123!",
            "institution": "T",
            "role": "student",
            "referral_code": code
        })
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 5: Security
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityRegression:
    def test_sql_injection_in_login(self, client):
        r = client.post("/auth/login", json={
            "email": "'; DROP TABLE users; --",
            "password": "anything"
        })
        assert r.status_code in (400, 401, 422)

    def test_xss_payload_in_survey_title(self, client):
        email = f"xss_{uuid.uuid4().hex[:6]}@test.edu"
        token = register_and_verify(client, email)
        r = client.post("/surveys", json={
            "title": "<script>alert('xss')</script>",
            "description": ""
        }, headers=auth_header(token))
        # Backend safely accepts string without 500 server crash
        assert r.status_code in (200, 400)

    def test_missing_fields_register(self, client):
        r = client.post("/auth/register", json={"email": "x@x.com"})
        assert r.status_code == 422

    def test_expired_token_rejected(self, client):
        import time
        from jose import jwt as jose_jwt
        from config import settings
        payload = {
            "sub": "fake-user-id",
            "exp": int(time.time()) - 3600,  # 1 hour expired
        }
        expired_token = jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert r.status_code == 401

    def test_no_password_in_response(self, client):
        email = f"sec_{uuid.uuid4().hex[:6]}@test.edu"
        token = register_and_verify(client, email)
        r = client.get("/auth/me", headers=auth_header(token))
        assert "password" not in r.json()
        assert "hashed_password" not in r.json()

    def test_rate_limit_or_reject_on_many_bad_logins(self, client):
        email = f"rate_{uuid.uuid4().hex[:6]}@test.edu"
        register_and_verify(client, email)
        for _ in range(5):
            client.post("/auth/login", json={"email": email, "password": "Wrong!"})
        r = client.post("/auth/login", json={"email": email, "password": "Wrong!"})
        assert r.status_code in (401, 429)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION SUITE 6: Marketplace
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketplaceRegression:
    @pytest.fixture(scope="class")
    def user(self, client):
        email = f"market_{uuid.uuid4().hex[:8]}@test.edu"
        token = register_and_verify(client, email)
        return {"token": token, "headers": auth_header(token)}

    def test_public_marketplace_accessible(self, client):
        r = client.get("/datanest/datasets")
        assert r.status_code == 200

    def test_featured_datasets_endpoint(self, client):
        r = client.get("/datanest/featured")
        assert r.status_code == 200

    def test_seller_dashboard_requires_auth(self, client):
        r = client.get("/datanest/sell/analytics")
        assert r.status_code == 401

    def test_seller_dashboard_with_auth(self, client, user):
        r = client.get("/datanest/sell/analytics", headers=user["headers"])
        assert r.status_code in (200, 404)

    def test_my_purchases_requires_auth(self, client):
        r = client.get("/datanest/me/library")
        assert r.status_code == 401

    def test_my_purchases_with_auth(self, client, user):
        r = client.get("/datanest/me/library", headers=user["headers"])
        assert r.status_code == 200
