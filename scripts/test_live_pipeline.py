import httpx
import asyncio
import os
from pathlib import Path
import time

# --- Configuration ---
API_BASE_URL = "http://localhost:8000"
HEALTH_CHECK_URL = f"{API_BASE_URL}/health"
TEST_USER = "pipeline-tester@example.com"
TEST_PASSWORD = "Password123!"
AUDIO_FILE_PATH = Path(__file__).parent / "test.wav"

async def wait_for_backend():
    """Poll the health check endpoint until the backend is ready."""
    print("🔄 Waiting for backend to be healthy...")
    start_time = time.time()
    while time.time() - start_time < 60:  # 60-second timeout
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(HEALTH_CHECK_URL)
                if response.status_code == 200 and response.json().get("status") == "healthy":
                    print("✅ Backend is healthy!")
                    return True
        except httpx.ConnectError:
            pass # Backend is not up yet
        await asyncio.sleep(2)
    print("❌ Timeout: Backend did not become healthy within 60 seconds.")
    return False

async def main():
    if not await wait_for_backend():
        return

    # Create a dummy WAV file (1-second silence)
    wav_header = bytes([
        82, 73, 70, 70, 44, 1, 0, 0, 87, 65, 86, 69, 102, 109, 116, 32, 16, 0, 0, 0, 1, 0, 1, 0,
        68, 172, 0, 0, 136, 88, 1, 0, 2, 0, 16, 0, 100, 97, 116, 97, 16, 1, 0, 0
    ])
    silence_data = bytes([0] * 16000)
    with open(AUDIO_FILE_PATH, "wb") as f:
        f.write(wav_header + silence_data)
    print(f"✅ Created dummy audio file at: {AUDIO_FILE_PATH}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"🔄 Registering test user: {TEST_USER}...")
            await client.post(
                f"{API_BASE_URL}/api/v1/auth/register",
                json={"email": TEST_USER, "password": TEST_PASSWORD, "full_name": "Pipeline Tester", "role": "Manager"},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                print("   (User already exists, proceeding to login)")
            else:
                raise

        print("🔄 Logging in...")
        login_resp = await client.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD},
        )
        login_resp.raise_for_status()
        token = login_resp.cookies.get("accessToken")
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login successful.")

        print("🔄 Creating a new meeting...")
        meeting_resp = await client.post(
            f"{API_BASE_URL}/api/v1/meetings/",
            headers=headers,
            json={
                "title": "Live Pipeline Test Meeting",
                "start_time": "2026-03-01T10:00:00Z",
                "end_time": "2026-03-01T11:00:00Z",
                "participants": []
            },
        )
        meeting_resp.raise_for_status()
        meeting_id = meeting_resp.json()["id"]
        print(f"✅ Meeting created with ID: {meeting_id}")

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
        print("\n🚀 PIPELINE TRIGGERED!")
        print("-" * 50)
        print("To monitor the process, run this command in a new terminal:")
        print("  docker-compose logs -f celery-worker")
        print("\nLook for logs related to 'Running Diarization...', 'Running Whisper...', and 'Starting analysis...'.")
        print("-" * 50)
    
    os.remove(AUDIO_FILE_PATH)


if __name__ == "__main__":
    asyncio.run(main())
