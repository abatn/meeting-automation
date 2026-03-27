import asyncio
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash

async def force_reset_password():
    email = "batniniabdelkader@yahoo.com"
    new_password = "Abdel15121978!"
    
    print(f"--- 🔐 Password Reset for {email} ---")
    
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.email == email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            print("❌ User not found in database!")
            return
            
        hashed_pw = get_password_hash(new_password)
        
        await db.execute(
            update(User)
            .where(User.email == email)
            .values(hashed_password=hashed_pw)
        )
        
        await db.commit()
        print(f"✅ Success: Password for {email} has been reset.")
        print("You can now login with your new credentials.")

if __name__ == "__main__":
    asyncio.run(force_reset_password())
