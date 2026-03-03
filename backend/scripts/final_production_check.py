import asyncio
import httpx
import boto3
import redis
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.user import User

async def check_infrastructure():
    print("--- 🛡️ INFRASTRUCTURE AUDIT (ISO 27001) ---")
    
    # 1. Database & Encryption Check
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).limit(1))
            print("✅ Postgres: Connected")
            if len(settings.SECRET_KEY) < 32:
                print("⚠️ Security: SECRET_KEY might be too short!")
            else:
                print("✅ Security: SECRET_KEY strength verified")
    except Exception as e:
        print(f"❌ Postgres: Failed - {e}")

    # 2. Redis & Cache Check
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        print("✅ Redis: Connected & Responsive")
    except Exception as e:
        print(f"❌ Redis: Failed - {e}")

    # 3. S3 / Minio Audit
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY
        )
        s3.list_buckets()
        print("✅ Minio (S3): Connected & Permissions OK")
    except Exception as e:
        print(f"❌ Minio (S3): Failed - {e}")

async def check_api_integrations():
    print("\n--- 🤖 AI & AUTOMATION INTEGRATION CHECK ---")
    
    # 1. Backend Health
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get("http://localhost:8000/health")
            if res.status_code == 200:
                print("✅ Backend API: Healthy")
            else:
                print(f"❌ Backend API: Status {res.status_code}")
        except Exception as e:
            print(f"❌ Backend API: Unreachable - {e}")

    # 2. n8n Security Callback Check (Audit Skill)
    try:
        secret = settings.INTERNAL_API_SECRET
        url = f"http://localhost:8000/api/v1/reports/automation/meeting/non-existent-id?x_secret={secret}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            if res.status_code == 404:
                print("✅ n8n Automation Auth: Secret-Key Authentication verified")
            elif res.status_code == 403:
                print("❌ n8n Automation Auth: Secret-Key REJECTED")
            else:
                print(f"⚠️ n8n Automation Auth: Unexpected Status {res.status_code}")
    except Exception as e:
        print(f"❌ n8n Automation Auth: Check failed - {e}")

if __name__ == "__main__":
    asyncio.run(check_infrastructure())
    asyncio.run(check_api_integrations())
