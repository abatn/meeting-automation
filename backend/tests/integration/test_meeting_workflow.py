import pytest
import struct
from httpx import AsyncClient
from tests.e2e.conftest import mock_gladia, mock_mistral_pv, mock_sentinel, mock_n8n_transcription

def _create_wav_bytes():
    """Create a valid minimal WAV file (1 second of silence at 16kHz)."""
    sample_rate = 16000
    duration = 1
    num_samples = sample_rate * duration
    data_size = num_samples * 2
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16, 1, 1, sample_rate,
        sample_rate * 2, 2, 16, b'data', data_size,
    )
    return header + b'\x00' * data_size

@pytest.mark.asyncio
async def test_full_meeting_flow(client: AsyncClient, test_user_data, test_meeting_data, mock_gladia, mock_mistral_pv, mock_sentinel, mock_n8n_transcription):
    # 1. Register/Login
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # 2. Create Meeting
    m_resp = await client.post("/api/v1/meetings/", json=test_meeting_data)
    assert m_resp.status_code == 201
    meeting_id = m_resp.json()["id"]
    
    # 3. Upload Recording (valid WAV format)
    audio_bytes = _create_wav_bytes()
    r_resp = await client.post(
        f"/api/v1/recordings/upload/{meeting_id}",
        files={"file": ("test.wav", audio_bytes, "audio/wav")}
    )
    assert r_resp.status_code in [200, 201, 202]
    
    # 4. Check Status (Integrated Mock)
    s_resp = await client.get(f"/api/v1/meetings/{meeting_id}")
    assert s_resp.status_code == 200
