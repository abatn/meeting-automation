import asyncio
import httpx
import json
import os
import sys

# Simulation der End-to-End Logik im Backend
async def test_full_pipeline():
    print("--- 🚀 STARTING FULL PIPELINE TEST ---")
    
    # 1. Check DB Connectivity
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.meeting import Meeting
    
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Meeting).limit(1))
            print("✅ Database: Connected")
    except Exception as e:
        print(f"❌ Database: Failed - {e}")
        return

    # 2. Check AI Environment
    from app.core.config import settings
    if settings.OPENAI_API_KEY:
        print("✅ OpenAI Key: Configured")
    else:
        print("❌ OpenAI Key: MISSING (Will fail transcription)")

    if settings.MISTRAL_API_KEY:
        print("✅ Mistral Key: Configured")
    else:
        print("❌ Mistral Key: MISSING (Will fail PV generation)")

    # 3. Simulate Transcription Task
    # We use a dummy recording ID that we created earlier in my test session
    from app.tasks.transcription_tasks import process_recording
    print("⏳ Triggering AI Pipeline Task...")
    
    # Note: This will actually call OpenAI/Mistral if keys are valid!
    # Since we can't wait for a real Celery worker here easily, we call the async function directly
    from app.tasks.transcription_tasks import _process_recording_pipeline
    
    try:
        # Assuming 'rec-test-123' exists from my previous step
        await _process_recording_pipeline('rec-test-123')
        print("🏁 Pipeline Test Task finished (check logs for AI response status)")
    except Exception as e:
        print(f"⚠️ Pipeline Task errored (expected if audio file is dummy): {e}")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
