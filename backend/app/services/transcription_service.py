import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def transcribe_audio(audio_content: bytes, filename: str, word_timestamps: bool = False) -> dict:
    """
    Transcribes audio content using the OpenAI Whisper API.
    If word_timestamps is True, returns detailed verbose_json with words.
    Otherwise, returns simple text string under 'text' key.
    Returns:
    { "text": "...", "words": [{"word": "Hallo", "start": 0.5, "end": 1.0}, ...] }
    """
    try:
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        files = {
            "file": (filename, audio_content),
        }
        data = {
            "model": "whisper-1"
        }
        
        if word_timestamps:
            data["response_format"] = "verbose_json"
            data["timestamp_granularities[]"] = "word"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
                timeout=300.0
            )
            response.raise_for_status()
            
            result = response.json()
            if word_timestamps:
                # result contains 'text' and 'words'
                return {
                    "text": result.get("text", ""),
                    "words": result.get("words", [])
                }
            else:
                return {
                    "text": result.get("text", ""),
                    "words": []
                }
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise