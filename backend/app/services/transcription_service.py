import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def transcribe_audio(audio_content: bytes, filename: str) -> str:
    """
    Transcribes audio content using the OpenAI Whisper API.
    """
    try:
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        files = {
            "file": (filename, audio_content),
            "model": (None, "whisper-1"),
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                timeout=300.0
            )
            response.raise_for_status()
            return response.json().get("text", "")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise