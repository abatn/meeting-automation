import httpx
import asyncio
import json

async def test_analytics():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Login as DG
    login_data = {"username": "dg@meeting.tn", "password": "password123"}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/auth/login", data=login_data)
        if response.status_code != 200:
            print(f"Login failed: {response.text}")
            return
        
        token = response.cookies.get("accessToken")
        headers = {"Authorization": f"Bearer {token}"}
        
        print("\n--- Testing GET /actions/patterns ---")
        response = await client.get(f"{base_url}/actions/patterns", headers=headers)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        print("\n--- Testing GET /actions/statistics/recurring ---")
        response = await client.get(f"{base_url}/actions/statistics/recurring", headers=headers)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_analytics())
