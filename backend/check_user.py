import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.client import Client

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(User, Client).join(Client, User.client_id == Client.id).where(User.email == 'batniniabdelkader@yahoo.com')
        res = await db.execute(stmt)
        row = res.first()
        if row:
            user, client = row
            print(f"--- USER VERIFICATION ---")
            print(f"Email:  {user.email}")
            print(f"Client: {client.company_name} (ID: {user.client_id})")
            print(f"Role:   {user.role}")
            print(f"-------------------------")
        else:
            print("USER NOT FOUND")

if __name__ == "__main__":
    asyncio.run(check())
