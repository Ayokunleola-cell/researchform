import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from api.models.database import Base, User
from config import settings
from passlib.context import CryptContext
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def init_db():
    print(f"Setting up database at {settings.DATABASE_URL}...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")
        
    # Create demo user
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "demo@researchform.app"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("Creating demo user...")
            demo_user = User(
                id="demo-user-0001",
                email="demo@researchform.app",
                full_name="Demo Researcher",
                institution="University of Lagos",
                role="researcher",
                hashed_password=pwd_context.hash("demo1234")
            )
            session.add(demo_user)
            await session.commit()
            print("Demo user created (demo@researchform.app / demo1234)")
        else:
            print("Demo user already exists.")
            
    await engine.dispose()
    print("Database setup complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
