import httpx
import logging
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class WhisperClient:
    def __init__(self):
        self.whisper_api_url = settings.WHISPER_API_URL
        self.timeout = settings.WHISPER_API_TIMEOUT_SECONDS
        if not self.whisper_api_url:
            logger.error("WHISPER_API_URL is not configured. Transcription service will not function.")
            raise ValueError("WHISPER_API_URL is not configured.")

    @retry(
        stop=stop_after_attempt(settings.WHISPER_API_RETRIES),
        wait=wait_fixed(settings.WHISPER_API_RETRY_DELAY_SECONDS),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True
    )
    async def call_whisper_api(
        self,
        audio_file_url: str,
        language: Optional[str] = None,
        enable_diarization: bool = False
    ) -> Dict[str, Any]:
        """
        Calls the external Whisper API to transcribe an audio file.
        
        Args:
            audio_file_url: The URL of the audio file to transcribe.
            language: Optional language hint for Whisper (e.g., "en", "de").
            enable_diarization: Whether to enable speaker diarization.
            
        Returns:
            A dictionary containing the transcription result.
            
        Raises:
            httpx.HTTPStatusError: If the API returns a non-2xx status code.
            httpx.RequestError: For network-related errors.
            ValueError: If WHISPER_API_URL is not configured.
        """
        if not self.whisper_api_url:
            raise ValueError("Whisper API URL is not configured.")

        payload = {
            "audio_url": audio_file_url,
            "language": language,
            "enable_diarization": enable_diarization
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info(f"Calling Whisper API at {self.whisper_api_url} with payload: {payload}")
                response = await client.post(self.whisper_api_url, json=payload)
                response.raise_for_status() # Raise an exception for 4xx/5xx responses
                
                result = response.json()
                logger.info(f"Whisper API call successful. Response keys: {result.keys()}")
                return result
            except httpx.HTTPStatusError as e:
                logger.error(f"Whisper API returned error status {e.response.status_code}: {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Network error calling Whisper API: {e}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred during Whisper API call: {e}")
                raise

whisper_client = WhisperClient()