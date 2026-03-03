import httpx
import asyncio
import time
import uuid
import os

BASE_URL = "http://localhost:8000/api/v1"
TEST_AUDIO_PATH = os.path.join(os.path.dirname(__file__), '..', 'test_audio.wav')

# Generate unique user credentials
unique_id = str(uuid.uuid4())
USER_EMAIL = f"testuser_{unique_id}@example.com"
USER_PASSWORD = "a_secure_password_123"

async def main():
    print("Waiting 15 seconds for services to start...")
    await asyncio.sleep(15)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # 1. Register a new user
            print(f"Registering user {USER_EMAIL}...")
            register_response = await client.post(
                "/auth/register",
                json={"email": USER_EMAIL, "password": USER_PASSWORD, "full_name": "E2E Test User"}
            )
            register_response.raise_for_status()
            print("User registered successfully.")

            # 2. Log in to get the token
            print("Logging in...")
            login_response = await client.post(
                "/auth/login/token",
                data={"username": USER_EMAIL, "password": USER_PASSWORD}
            )
            login_response.raise_for_status()
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("Login successful.")

            # 3. Create a meeting
            print("Creating a new meeting...")
            meeting_data = {
                "title": "E2E Pipeline Test Meeting",
                "start_time": "2026-03-01T10:00:00",
                "end_time": "2026-03-01T11:00:00"
            }
            meeting_response = await client.post(
                "/meetings/",
                json=meeting_data,
                headers=headers
            )
            meeting_response.raise_for_status()
            meeting_id = meeting_response.json()["id"]
            print(f"Meeting created with ID: {meeting_id}")

            # 4. Upload the audio file
            print(f"Uploading audio file '{TEST_AUDIO_PATH}'...")
            if not os.path.exists(TEST_AUDIO_PATH):
                print(f"ERROR: Test audio file not found at {TEST_AUDIO_PATH}")
                return

            with open(TEST_AUDIO_PATH, "rb") as f:
                upload_response = await client.post(
                    f"/recordings/upload/{meeting_id}",
                    files={"file": (os.path.basename(TEST_AUDIO_PATH), f, "audio/wav")},
                    headers=headers
                )
                upload_response.raise_for_status()
            
            recording_id = upload_response.json()["id"]
            print(f"Audio uploaded successfully. Recording ID: {recording_id}")

            # 5. Poll for transcription status
            print("Polling for transcription status...")
            status = ""
            while status not in ["completed", "failed"]:
                await asyncio.sleep(5)
                status_response = await client.get(
                    f"/transcriptions/status/{recording_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                data = status_response.json()
                status = data.get("status")
                progress = data.get("progress", 0)
                print(f"Current status: {status}, Progress: {progress}%")

            # 6. Fetch final result
            print(f"Pipeline finished with status: {status}")
            if status == "completed":
                result_response = await client.get(
                    f"/transcriptions/{recording_id}",
                    headers=headers
                )
                result_response.raise_for_status()
                transcription_result = result_response.json()
                print("--- Transcription Result ---")
                print(transcription_result.get("full_text"))
                print("--------------------------")
            else:
                print("Transcription failed. Check the logs for details.")

        except httpx.HTTPStatusError as e:
            print(f"An error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"A critical error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
