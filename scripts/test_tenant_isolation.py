import requests
import uuid

BASE_URL = "http://localhost:8000/api/v1"
PASS = "Password123!"

def get_token(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": email, "password": password})
    if resp.status_code != 200:
        return None
    return resp.cookies.get("accessToken")

def run_test():
    print("🧪 Starting Multi-Tenant Isolation Test...")
    
    # 1. Setup Identities
    # Client A (Meeting Automation)
    token_a = get_token("admin@meeting.tn", PASS)
    # Client B (Pro)
    token_b = get_token("admin@pro.tn", PASS)
    
    if not token_a or not token_b:
        print("❌ Error: Could not get tokens for both clients.")
        return

    # 2. Baseline
    def get_count(token):
        # Clear cache before each fetch to be sure
        import os
        os.system("docker compose exec -T redis redis-cli -a redis_password KEYS 'reports_*' | xargs -r docker compose exec -T redis redis-cli -a redis_password DEL > /dev/null 2>&1")
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/reports/dashboard/dg", headers=headers)
        return r.json().get("meeting_stats", {}).get("total", 0)

    count_a_before = get_count(token_a)
    count_b_before = get_count(token_b)
    
    print(f"📊 Initial Counts -> Client A: {count_a_before}, Client B: {count_b_before}")

    # 3. Action: Create Meeting in Client B (Current Month)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    meeting_payload = {
        "title": f"Secret Meeting Client B {uuid.uuid4().hex[:4]}",
        "start_time": "2026-03-31T10:00:00", # TODAY
        "status": "planned"
    }
    create_resp = requests.post(f"{BASE_URL}/meetings/", json=meeting_payload, headers=headers_b)
    if create_resp.status_code != 201:
        print(f"❌ Error creating meeting: {create_resp.text}")
        return
    print("✅ Created new meeting in Client B")

    # 4. Verification
    count_a_after = get_count(token_a)
    count_b_after = get_count(token_b)
    
    print(f"📊 Final Counts -> Client A: {count_a_after}, Client B: {count_b_after}")

    # Isolation Check
    if count_a_after == count_a_before and count_b_after == count_b_before + 1:
        print("✨ SUCCESS: Physical Tenant Isolation verified! Data creation in Client B does not affect Client A.")
    else:
        print("❌ FAILURE: Isolation Breach or Count Sync Error detected.")

if __name__ == "__main__":
    run_test()
