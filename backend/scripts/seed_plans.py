import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.models.client import Client, SubscriptionPlan, SubscriptionStatus
from app.models.user import User, Role, UserStatus
from app.core.security import get_password_hash
from sqlalchemy import select

async def seed_plans():
    print("--- 🚀 Creating Test Tenants for all Plans ---")
    async with AsyncSessionLocal() as db:
        # Get Admin Role
        role_stmt = select(Role).where(Role.name == "admin")
        role = (await db.execute(role_stmt)).scalar_one_or_none()
        if not role:
            role = Role(id=str(uuid.uuid4()), name="admin", description="Tenant Admin")
            db.add(role)
            await db.flush()

        plans = [
            {"name": "Gratuit Corp", "plan": SubscriptionPlan.GRATUIT, "email": "admin@free.tn", "mins": 600},
            {"name": "Pro Services", "plan": SubscriptionPlan.PRO, "email": "admin@pro.tn", "mins": 3000},
            {"name": "Enterprise Global", "plan": SubscriptionPlan.ENTREPRISE, "email": "admin@enterprise.tn", "mins": 12000},
        ]

        password = "Password123!"
        hashed_pw = get_password_hash(password)

        for p in plans:
            # Create Client
            client = Client(
                id=str(uuid.uuid4()),
                company_name=p["name"],
                subscription_plan=p["plan"],
                subscription_status=SubscriptionStatus.ACTIVE,
                minutes_included=p["mins"]
            )
            db.add(client)
            await db.flush()

            # Create Admin User
            user = User(
                id=str(uuid.uuid4()),
                client_id=client.id,
                email=p["email"],
                full_name=f"{p['plan'].capitalize()} Admin",
                hashed_password=hashed_pw,
                status=UserStatus.ACTIVE.value
            )
            user.roles.append(role)
            db.add(user)
            print(f"✅ Created: {p['name']} -> Login: {p['email']} (Plan: {p['plan']}, Limit: {p['mins']} min)")

        await db.commit()
        print("--- ✨ All test tenants are ready! ---")

if __name__ == "__main__":
    asyncio.run(seed_plans())
