import httpx
import asyncio
import os
from pathlib import Path
import time
import sys

API_BASE_URL = "http://localhost:8000"
TEST_USER = "e2e-tester@example.com"
TEST_PASSWORD = "StrongPassword123!"
AUDIO_FILE_PATH = Path(__file__).parent / "test_audio.wav"

async def main():
    AUDIO_FILE_PATH = Path(__file__).parent / "test_beep.wav"
    if not AUDIO_FILE_PATH.exists():
        print(f"❌ Audio file not found: {AUDIO_FILE_PATH}")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 2. Register
        print(f"🔄 Registering test user: {TEST_USER}...")
        try:
            await client.post(
                f"{API_BASE_URL}/api/v1/auth/register",
                json={"email": TEST_USER, "password": TEST_PASSWORD, "full_name": "E2E Tester", "role": "manager"},
            )
        except httpx.HTTPStatusError as e:
            pass

        # 3. Login
        print("🔄 Logging in...")
        login_resp = await client.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD},
        )
        login_resp.raise_for_status()
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login successful.")

        # 4. Create Meeting
        print("🔄 Creating a new meeting...")
        meeting_resp = await client.post(
            f"{API_BASE_URL}/api/v1/meetings/",
            headers=headers,
            json={
                "title": "Live Pipeline E2E Meeting",
                "start_time": "2026-03-01T10:00:00Z",
                "end_time": "2026-03-01T11:00:00Z",
                "participants": []
            },
        )
        meeting_resp.raise_for_status()
        meeting_id = meeting_resp.json()["id"]
        print(f"✅ Meeting created with ID: {meeting_id}")

        # 5. Upload Audio
        print(f"🔄 Uploading audio file to trigger the pipeline...")
        with open(AUDIO_FILE_PATH, "rb") as f:
            upload_resp = await client.post(
                f"{API_BASE_URL}/api/v1/recordings/upload/{meeting_id}",
                headers=headers,
                files={"file": ("test.wav", f, "audio/wav")},
            )
            upload_resp.raise_for_status()
        
        recording_id = upload_resp.json()["id"]
        print(f"✅ Audio uploaded. Recording ID: {recording_id}")
        
        # 6. Poll for transcription status
        print("🔄 Polling for pipeline status...")
        status = "processing"
        
        # Polling DB directly for the recording status as the status endpoint might be WebSocket based
        # Let's hit the backend DB directly via a protected endpoint if we can, 
        # or we check the transcription status if there's an endpoint.
        # Actually, let's poll the recording object:
        for _ in range(30):
            await asyncio.sleep(5)
            # The API doesn't seem to have a simple get_recording GET /api/v1/recordings/{id} yet, 
            # let's fetch the meeting and see its status, or wait.
            print("⏳ Pipeline running in background...")
            
            # Since the celery worker runs in another container, we give it ~30 seconds for OpenAI/Mistral
            # We can check the DB via a quick SQL query since we are inside the container:
            from app.core.database import AsyncSessionLocal
            from app.models.recording import Recording
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Recording).where(Recording.id == recording_id))
                rec = result.scalar_one_or_none()
                if rec:
                    print(f"   Current DB Status: {rec.status}")
                    if rec.status in ['completed', 'failed']:
                        status = rec.status
                        break

        print(f"🏁 Pipeline finished with status: {status}")
        
        if status == 'completed':
            print("✅ E2E TEST PASSED! The pipeline triggered Whisper, Mistral, and successfully completed.")
            # Show PV
            from app.core.database import AsyncSessionLocal
            from app.models.transcription import Transcription
            from app.models.action import Action
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Transcription).where(Transcription.recording_id == recording_id))
                trans = result.scalar_one_or_none()
                if trans:
                    print(f"📜 Transcription Text: {trans.full_text}")
                
                result = await db.execute(select(Action).where(Action.meeting_id == meeting_id))
                actions = result.scalars().all()
                if actions:
                    print(f"✅ Extracted {len(actions)} Action Items from PV!")
        else:
            print("❌ E2E TEST FAILED OR TIMED OUT.")
            sys.exit(1)

    os.remove(AUDIO_FILE_PATH)

if __name__ == "__main__":
    asyncio.run(main())