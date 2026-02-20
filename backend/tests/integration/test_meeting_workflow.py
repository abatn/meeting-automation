import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_full_meeting_lifecycle(client: AsyncClient, db_session: AsyncSession, normal_user_token_headers):
    # 1. Meeting erstellen -> n8n Webhook getriggert?
    meeting_data = {
        "title": "Strategy Workshop 2026",
        "description": "Annual strategy planning meeting",
        "start_time": "2026-03-01T10:00:00",
        "end_time": "2026-03-01T11:00:00",
        "location": "Conference Room A"
    }
    
    with patch("app.services.meeting_service.httpx.AsyncClient.post") as mock_n8n:
        mock_n8n.return_value = MagicMock(status_code=200)
        
        response = await client.post(
            "/api/v1/meetings/",
            json=meeting_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 201
        meeting_id = response.json()["id"]
        
        # Check if n8n was called
        assert mock_n8n.called

    # 2. Audio hochladen -> Transkription starten?
    files = {'file': ('test_audio.wav', b'audio content', 'audio/wav')}
    
    with patch("app.tasks.transcription_tasks.transcribe_audio_task.delay") as mock_task:
        response = await client.post(
            f"/api/v1/recordings/upload/{meeting_id}",
            files=files,
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert mock_task.called

    # 3. PV generieren -> Action-Items extrahiert?
    pv_data = {
        "meeting_id": meeting_id,
        "content": "Meeting summary: We decided to expand to the Maghreb region.",
        "generated_at": "2026-03-01T12:00:00"
    }
    
    with patch("app.services.pv_service.PVService.extract_actions") as mock_extract:
        mock_extract.return_value = [{"description": "Market research", "assigned_to": "Ahmed"}]
        
        response = await client.post(
            "/api/v1/pv/",
            json=pv_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 201
        assert mock_extract.called

    # 4. Action zuweisen -> WhatsApp Reminder?
    action_id = 1 # Assuming first action
    with patch("app.services.action_service.httpx.AsyncClient.post") as mock_whatsapp:
        mock_whatsapp.return_value = MagicMock(status_code=200)
        
        response = await client.post(
            f"/api/v1/actions/{action_id}/remind",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert mock_whatsapp.called