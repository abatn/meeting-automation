import httpx
import asyncio
import uuid

async def test_registration_dg_assignment():
    print("--- 🧪 Testing Auto-DG Assignment for New Tenants ---")
    
    unique_email = f"tenant_admin_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": unique_email,
        "password": "TestPassword123!",
        "full_name": "New Tenant DG",
        "company_name": f"Company {uuid.uuid4().hex[:6]}",
        "plan": "PRO"
    }
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Register new tenant
        print(f"Registering new user: {unique_email} (New Tenant)")
        response = await client.post("/api/v1/auth/register", json=payload)
        
        if response.status_code != 201:
            print(f"❌ Registration failed: {response.text}")
            return

        data = response.json()
        print(f"✅ Registration successful. Assigned role: {data.get('role')}")
        
        if data.get("role") == "dg":
            print("✨ SUCCESS: User automatically assigned 'dg' role.")
        else:
            print(f"❌ FAILURE: User assigned '{data.get('role')}' role instead of 'dg'.")

if __name__ == "__main__":
    asyncio.run(test_registration_dg_assignment())
