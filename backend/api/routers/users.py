# backend/api/routers/users.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from api.deps import get_current_user, get_db
from api.models.database import User
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import shutil

router = APIRouter()

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    photo_url = f"/storage/avatars/{user.avatar_path}" if user.avatar_path else None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "institution": user.institution,
        "role": user.role,
        "photo_url": photo_url,
        "preferences": user.preferences or {}
    }

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    preferences: Optional[dict] = None

@router.patch("/me")
async def update_me(
    data: ProfileUpdate, 
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.institution is not None:
        user.institution = data.institution
    if data.role is not None:
        user.role = data.role
    if data.preferences is not None:
        user.preferences = data.preferences
        
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    photo_url = f"/storage/avatars/{user.avatar_path}" if user.avatar_path else None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "institution": user.institution,
        "role": user.role,
        "photo_url": photo_url,
        "preferences": user.preferences or {}
    }

@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an image.")
        
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join("storage", "avatars", filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Delete old avatar if it exists
    if user.avatar_path:
        old_path = os.path.join("storage", "avatars", user.avatar_path)
        if os.path.exists(old_path):
            os.remove(old_path)
            
    user.avatar_path = filename
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {"photo_url": f"/storage/avatars/{filename}"}
