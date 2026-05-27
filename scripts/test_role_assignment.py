import httpx
import asyncio
import uuid

async def test_role_assignment():
    print("--- 🧪 Testing Role Assignment for Invited Members ---")
    
    # 1. Get Admin Token
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        login_res = await client.post("/api/v1/auth/login", data={
            "username": "admin@meeting.tn",
            "password": "Password123!"
        })
        token = login_res.cookies.get("accessToken")
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Invite a MANAGER
        manager_email = f"manager_{uuid.uuid4().hex[:6]}@example.com"
        print(f"Inviting MANAGER: {manager_email}")
        res = await client.post("/api/v1/team/", headers=headers, json={
            "email": manager_email,
            "full_name": "Test Manager",
            "role": "manager",
            "position": "Lead"
        })
        if res.status_code == 200 or res.status_code == 201:
            print(f"✅ Manager invitation sent. Role in response: {res.json().get('role')}")
        else:
            print(f"❌ Manager invitation failed: {res.text}")

        # 3. Try to invite a SYSTEM_ADMIN (Should fail)
        print("Testing unauthorized role (system_admin)...")
        res_fail = await client.post("/api/v1/team/", headers=headers, json={
            "email": "hacker@example.com",
            "full_name": "Hacker",
            "role": "system_admin"
        })
        if res_fail.status_code == 400:
            print("✅ Successfully blocked unauthorized role assignment (400 Bad Request).")
        else:
            print(f"❌ Security Failure: System allowed system_admin assignment! Status: {res_fail.status_code}")

if __name__ == "__main__":
    asyncio.run(test_role_assignment())
