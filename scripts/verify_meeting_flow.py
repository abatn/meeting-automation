import requests
import time
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def test_pipeline():
    print("🚀 Starting ISS Pipeline E2E Test...")
    
    # 1. Login
    login_data = {"username": "admin@meeting.tn", "password": "Password123!"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")

    # 2. Create Meeting
    meeting_payload = {
        "title": "ISS Pipeline Benchmark Test",
        "start_time": "2026-03-27T10:00:00",
        "status": "planned"
    }
    create_resp = requests.post(f"{BASE_URL}/meetings/", json=meeting_payload, headers=headers)
    meeting_id = create_resp.json()["id"]
    print(f"✅ Meeting created: {meeting_id}")

    # 3. Simulate Recording Upload
    # Create a small dummy wav file
    with open("test_audio.wav", "wb") as f:
        f.write(b"RIFF" + b"\0" * 1000)
    
    print("🎙️ Uploading audio...")
    start_time = time.time()
    files = {'file': ('test_audio.wav', open('test_audio.wav', 'rb'), 'audio/wav')}
    upload_resp = requests.post(f"{BASE_URL}/recordings/upload/{meeting_id}", files=files, headers=headers)
    
    if upload_resp.status_code != 200:
        print(f"❌ Upload failed: {upload_resp.text}")
        return

    recording_id = upload_resp.json()["id"]
    print(f"✅ Upload successful. Recording ID: {recording_id}")

    # 4. Poll for Completion (33.3s target)
    print("⏳ Waiting for AI Synthesis...")
    completed = False
    for i in range(60): # 60 seconds timeout
        status_resp = requests.get(f"{BASE_URL}/recordings/{recording_id}", headers=headers)
        status = status_resp.json()["status"]
        if status == "completed":
            duration = time.time() - start_time
            print(f"✨ PIPELINE SUCCESS! Time-to-Deliver: {duration:.1f}s")
            completed = True
            break
        time.sleep(1)

    if not completed:
        print("❌ Test timed out after 60s")

if __name__ == "__main__":
    test_pipeline()
