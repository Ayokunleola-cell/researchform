# backend/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, EmailStr
from jose import jwt
from datetime import datetime, timedelta, timezone
import uuid
import random
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from api.deps import get_db, get_current_user, limiter
from api.models.database import User, UserRole, UserOTP
from services.email import send_otp_email
from config import settings

router = APIRouter()
_ph = PasswordHasher()

def hash_pw(pw: str) -> str:
    return _ph.hash(pw)

def verify_pw(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False

def make_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user.id, "email": user.email, "name": user.full_name, "exp": exp},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    institution: str = ""
    role: UserRole = UserRole.student
    department: str = ""
    referral_code: str = ""  # optional referral code from ?ref= query param

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str
    purpose: str # 'login' or 'register'

class CheckEmailRequest(BaseModel):
    email: EmailStr

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def user_out(u: User):
    photo_url = f"/storage/avatars/{u.avatar_path}" if u.avatar_path else None
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "institution": u.institution, "role": u.role, "created_at": str(u.created_at),
        "referral_code": u.referral_code or "",
        "photo_url": photo_url,
    }

@router.post("/register")
@limiter.limit("3/minute")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "allow_registrations"))
    allow = setting.scalar_one_or_none()
    if allow and allow.value.lower() == "false":
        raise HTTPException(403, "New registrations are currently disabled by the administrator.")

    existing = await db.execute(select(User).where(User.email == data.email))
    user = existing.scalar_one_or_none()
    
    if user:
        if user.is_verified:
            raise HTTPException(400, "Email already registered")
        # If not verified, we can update their info and resend OTP
        user.full_name = data.full_name
        user.institution = data.institution
        user.hashed_password = hash_pw(data.password)
    else:
        # Generate a unique referral code for this new user
        import hashlib, base64 as _b64
        raw_code = _b64.b32encode(hashlib.sha256(str(uuid.uuid4()).encode()).digest())[:8].decode().upper()
        # Collision guard
        code_check = await db.execute(select(User).where(User.referral_code == raw_code))
        if code_check.scalar_one_or_none():
            raw_code = _b64.b32encode(hashlib.sha256(str(uuid.uuid4()).encode()).digest())[:8].decode().upper()

        user = User(
            id=str(uuid.uuid4()),
            email=data.email,
            full_name=data.full_name,
            institution=data.institution,
            role=data.role,
            hashed_password=hash_pw(data.password),
            is_verified=False,
            referral_code=raw_code,
            preferences={"department": data.department} if data.department else {}
        )

        # Link referral if code provided
        if data.referral_code:
            ref_result = await db.execute(
                select(User).where(User.referral_code == data.referral_code.upper().strip())
            )
            referrer = ref_result.scalar_one_or_none()
            if referrer and referrer.email != data.email:  # prevent self-referral
                user.referred_by_id = referrer.id

        db.add(user)
        
    await db.flush()

    # Bypass OTP for test emails
    if user.email.endswith("@test.com"):
        user.is_verified = True
        await db.commit()
        return {"access_token": make_token(user), "user": user_out(user)}

    # Invalidate old OTPs for this purpose
    await db.execute(delete(UserOTP).where(UserOTP.user_id == user.id, UserOTP.purpose == 'register'))
    
    otp_code = generate_otp()
    otp_record = UserOTP(
        user_id=user.id,
        otp_code=otp_code,
        purpose='register',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    db.add(otp_record)
    await db.commit()

    # Send email
    await send_otp_email(user.email, otp_code)
    
    return {"status": "pending_verification"}

@router.post("/check-email")
async def check_email(data: CheckEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    return {"exists": user is not None}

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_pw(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    # Bypass OTP for demo user and test emails
    if user.email == "demo@researchform.app" or user.email.endswith("@test.com"):
        return {"access_token": make_token(user), "user": user_out(user)}
        
    if getattr(user, "mfa_enabled", False):
        return {"status": "pending_verification", "mfa": True}

    # Invalidate old OTPs for login
    await db.execute(delete(UserOTP).where(UserOTP.user_id == user.id, UserOTP.purpose == 'login'))
    
    otp_code = generate_otp()
    otp_record = UserOTP(
        user_id=user.id,
        otp_code=otp_code,
        purpose='login',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    db.add(otp_record)
    await db.commit()

    # Send email
    await send_otp_email(user.email, otp_code)
    
    return {"status": "pending_verification"}

@router.post("/verify-otp")
@limiter.limit("10/minute")
async def verify_otp(request: Request, data: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    # Find user
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
        
    if data.purpose == 'login' and getattr(user, "mfa_enabled", False):
        if not user.mfa_secret:
            raise HTTPException(400, "MFA configured incorrectly")
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(data.otp_code):
            raise HTTPException(400, "Invalid authenticator code")
    else:
        # Find valid OTP
        otp_result = await db.execute(
            select(UserOTP).where(
                UserOTP.user_id == user.id,
                UserOTP.otp_code == data.otp_code,
                UserOTP.purpose == data.purpose,
                UserOTP.expires_at > datetime.now(timezone.utc)
            )
        )
        otp_record = otp_result.scalar_one_or_none()
        
        if not otp_record:
            raise HTTPException(400, "Invalid or expired verification code")
            
        # Delete the OTP so it can't be reused
        await db.execute(delete(UserOTP).where(UserOTP.id == otp_record.id))
    
    if not user.is_verified:
        user.is_verified = True
        
        # Give signup bonus only if they don't have a wallet already
        from decimal import Decimal
        from api.models.database import CreditWallet, CreditTransaction, CreditTransactionType, SystemSettings
        from config import settings as app_settings

        setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "signup_bonus_credits"))
        bonus_setting = setting.scalar_one_or_none()
        bonus_value = bonus_setting.value if bonus_setting else str(app_settings.SIGNUP_BONUS_CREDITS)
        bonus = Decimal(bonus_value)
        if bonus > 0:
            wallet_result = await db.execute(select(CreditWallet).where(CreditWallet.user_id == user.id))
            wallet = wallet_result.scalar_one_or_none()
            if not wallet:
                wallet = CreditWallet(user_id=user.id, balance=bonus)
                db.add(wallet)
                db.add(
                    CreditTransaction(
                        user_id=user.id,
                        amount=bonus,
                        type=CreditTransactionType.signup_bonus,
                        description=f"Welcome bonus - {bonus} analysis credits",
                        balance_after=bonus,
                        extra={"source": "verification"},
                    )
                )

    await db.commit()
    await db.refresh(user)
    return {"access_token": make_token(user), "user": user_out(user)}

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return user_out(current_user)

class EnableMFARequest(BaseModel):
    otp_code: str
    mfa_secret: str

@router.post("/mfa/setup")
async def mfa_setup(current_user: User = Depends(get_current_user)):
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name="ResearchForm")
    return {"secret": secret, "uri": uri}

@router.post("/mfa/enable")
async def mfa_enable(data: EnableMFARequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    totp = pyotp.TOTP(data.mfa_secret)
    if not totp.verify(data.otp_code):
        raise HTTPException(400, "Invalid authenticator code")
    current_user.mfa_secret = data.mfa_secret
    current_user.mfa_enabled = True
    db.add(current_user)
    await db.commit()
    return {"status": "success", "mfa_enabled": True}

@router.post("/mfa/disable")
async def mfa_disable(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    current_user.mfa_secret = None
    current_user.mfa_enabled = False
    db.add(current_user)
    await db.commit()
    return {"status": "success", "mfa_enabled": False}
