import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash

async def update_user_password():
    # --- Configuration ---
    target_email = "test@example.com"
    new_password = "test123"
    # -------------------

    print(f"--- 🔒 Attempting to update password for {target_email} ---")
    hashed_password = get_password_hash(new_password)

    async with AsyncSessionLocal() as db:
        # Find the user by email
        stmt = select(User).where(User.email == target_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update the password
            user.hashed_password = hashed_password
            await db.commit()
            print(f"--- ✅ Password for {target_email} updated successfully! ---")
        else:
            print(f"--- ❌ User with email {target_email} not found. ---")

if __name__ == "__main__":
    # Ensure the script is run within the context of the application's event loop
    # or use asyncio.run() for a standalone script.
    asyncio.run(update_user_password())
