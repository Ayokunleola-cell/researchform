import asyncio
from argon2 import PasswordHasher
from sqlalchemy import select
from api.deps import AsyncSessionLocal
from api.models.database import User
import uuid

_ph = PasswordHasher()

async def main():
    email = "demo@researchform.app"
    pwd = "Password123!"
    hashed = _ph.hash(pwd)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == email))
        u = res.scalar_one_or_none()
        if not u:
            print("Creating demo user...")
            u = User(
                id=str(uuid.uuid4()),
                email=email,
                hashed_password=hashed,
                full_name="Demo User",
                role="admin",
                is_verified=True
            )
            db.add(u)
        else:
            print("Demo user exists. Updating password...")
            u.hashed_password = hashed
            u.is_verified = True
            
        await db.commit()
        print(f"SUCCESS: Created/Updated demo user {email} with password: {pwd}")

if __name__ == "__main__":
    asyncio.run(main())
