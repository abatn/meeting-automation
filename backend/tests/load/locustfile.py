from locust import HttpUser, task, between

class MeetingAutomationUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login or setup here
        pass

    @task(3)
    def get_meetings(self):
        self.client.get("/api/v1/meetings/")

    @task(1)
    def create_meeting(self):
        self.client.post("/api/v1/meetings/", json={
            "title": "Load Test Meeting",
            "date": "2026-04-01T12:00:00",
            "participants": []
        })
