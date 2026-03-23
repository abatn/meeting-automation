import asyncio
import uuid
import sys
import os

# Set current working directory as part of PYTHONPATH for script to find 'app'
sys.path.append(os.getcwd())

from app.core.database import AsyncSessionLocal
from app.models.user import User, Role
from app.models.client import Client, SubscriptionPlan, SubscriptionStatus
from app.core.security import get_password_hash
from sqlalchemy import select

async def seed_data():
    print("--- 📝 Seeding System & Enterprise Users (Production Setup) ---")
    async with AsyncSessionLocal() as db:
        # 1. Create Roles (including system_admin and tech_admin)
        roles_data = [
            {"name": "system_admin", "description": "Global Business/System Administrator"},
            {"name": "tech_admin", "description": "Technical Administrator (Mission Control)"},
            {"name": "admin", "description": "Tenant Administrator"},
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
        
        await db.flush()

        # 2. Create a System Client (Required for isolation)
        stmt = select(Client).where(Client.company_name == "System Management")
        res = await db.execute(stmt)
        system_client = res.scalar_one_or_none()
        if not system_client:
            system_client = Client(
                id=str(uuid.uuid4()),
                company_name="System Management",
                subscription_plan=SubscriptionPlan.ENTREPRISE,
                subscription_status=SubscriptionStatus.ACTIVE,
                minutes_included=999999
            )
            db.add(system_client)
            await db.flush()
            print("Created System Management client")

        # 3. Create Users
        # Using Password123! as standardized test password
        password = "Password123!"
        hashed_pw = get_password_hash(password)

        users_data = [
            {
                "email": "admin@meeting.tn", 
                "name": "Global Business Admin", 
                "role": "system_admin", 
                "superuser": True
            },
            {
                "email": "tech@meeting.tn", 
                "name": "Mission Control Admin", 
                "role": "tech_admin", 
                "superuser": True
            },
            {
                "email": "batniniabdelkader@yahoo.com", 
                "name": "Abdelkader Batnini", 
                "role": "system_admin", 
                "superuser": True
            },
            {
                "email": "dg@meeting.tn", 
                "name": "Directeur Général", 
                "role": "dg", 
                "superuser": False
            },
            {
                "email": "manager@meeting.tn", 
                "name": "Chef de Département", 
                "role": "manager", 
                "superuser": False
            },
            {
                "email": "user@meeting.tn", 
                "name": "Collaborateur", 
                "role": "participant", 
                "superuser": False
            }
        ]
        
        for u_data in users_data:
            stmt = select(User).where(User.email == u_data["email"])
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    id=str(uuid.uuid4()),
                    client_id=system_client.id,
                    email=u_data["email"],
                    full_name=u_data["name"],
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=u_data["superuser"]
                )
                user.roles.append(role_objs[u_data["role"]])
                db.add(user)
                print(f"✅ Created user: {u_data['email']} (Role: {u_data['role']}, Superuser: {u_data['superuser']})")
            else:
                # Update existing user to ensure they have the correct permissions/roles and password
                user.is_superuser = u_data["superuser"]
                user.hashed_password = hashed_pw
                if role_objs[u_data["role"]] not in user.roles:
                    user.roles = [role_objs[u_data["role"]]]
                print(f"ℹ️ Updated existing user: {u_data['email']} (Password reset)")

        await db.commit()
        print("--- ✨ System Seeding completed! ---")
        print(f"Login: admin@meeting.tn / {password}")

if __name__ == "__main__":
    asyncio.run(seed_data())
