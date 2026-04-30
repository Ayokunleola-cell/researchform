# backend/api/routers/users.py
from fastapi import APIRouter, Depends
from api.deps import get_current_user
from api.models.database import User
router = APIRouter()

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id":user.id,"email":user.email,"full_name":user.full_name,
            "institution":user.institution,"role":user.role}
