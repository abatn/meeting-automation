import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.models.user import User, Role
from app.core.security import get_password_hash
from sqlalchemy import select

async def seed_data():
    print("--- 📝 Seeding Enterprise Test Users ---")
    async with AsyncSessionLocal() as db:
        # 1. Create Roles
        roles_data = [
            {"name": "dg", "description": "Director General"},
            {"name": "manager", "description": "Department Manager"},
            {"name": "participant", "description": "Regular Participant"}
        ]
        
        role_objs = {}
        for r_data in roles_data:
            stmt = select(Role).where(Role.name == r_data["name"])
            result = await db.execute(stmt)
            role = result.scalar_one_or_none()
            if not role:
                role = Role(id=str(uuid.uuid4()), name=r_data["name"], description=r_data["description"])
                db.add(role)
                print(f"Created role: {r_data['name']}")
            role_objs[r_data["name"]] = role
        
        await db.commit()

        # 2. Create Users
        users_data = [
            {"email": "dg@meeting.tn", "name": "Directeur Général", "role": "dg"},
            {"email": "manager@meeting.tn", "name": "Chef de Département", "role": "manager"},
            {"email": "user@meeting.tn", "name": "Collaborateur", "role": "participant"}
        ]
        
        password = "Password123!"
        hashed_pw = get_password_hash(password)

        for u_data in users_data:
            stmt = select(User).where(User.email == u_data["email"])
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    id=str(uuid.uuid4()),
                    email=u_data["email"],
                    full_name=u_data["name"],
                    hashed_password=hashed_pw,
                    is_active=True
                )
                user.roles.append(role_objs[u_data["role"]])
                db.add(user)
                print(f"Created user: {u_data['email']} (Password: {password})")
        
        await db.commit()
        print("--- ✅ Seeding completed! ---")

if __name__ == "__main__":
    asyncio.run(seed_data())
