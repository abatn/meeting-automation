import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from app.main import app

# Testing WebSockets with FastAPI TestClient
def test_websocket_connection():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/websockets/transcription/123") as websocket:
        data = websocket.receive_json()
        assert data == {"status": "connected", "progress": 0, "message": "Connection established"}
        
        # Test Ping/Pong
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"
