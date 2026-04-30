# backend/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import uuid, random, string

from api.deps import get_db, get_current_user
from api.models.database import User, UserRole
from config import settings

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def make_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def hash_pw(pw: str) -> str:  return pwd_ctx.hash(pw)
def verify_pw(plain, hashed) -> bool: return pwd_ctx.verify(plain, hashed)

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    institution: str = ""
    role: UserRole = UserRole.student

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

def user_out(u: User):
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "institution": u.institution, "role": u.role, "created_at": str(u.created_at),
    }

@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        full_name=data.full_name,
        institution=data.institution,
        role=data.role,
        hashed_password=hash_pw(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"access_token": make_token(user.id), "user": user_out(user)}

@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_pw(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": make_token(user.id), "user": user_out(user)}

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return user_out(current_user)
