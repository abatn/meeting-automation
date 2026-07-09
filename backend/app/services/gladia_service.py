import httpx
import logging
import asyncio
import time
import mimetypes
from app.core.config import settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

async def track_gladia_call(latency: float, success: bool):
    try:
        r = await get_redis_client()
        await r.incr("ai:gladia:calls")
        if not success:
            await r.incr("ai:gladia:errors")
        if latency > 0:
            await r.lpush("ai:gladia:latencies", latency)
            await r.ltrim("ai:gladia:latencies", 0, 99)
    except Exception as e:
        logger.error(f"Failed to track Gladia metrics: {e}")

class GladiaService:
    def __init__(self):
        self.api_key = settings.GLADIA_API_KEY
        self.base_url = "https://api.gladia.io/v2"

    async def transcribe_and_diarize(self, audio_file_path: str, num_room_participants: int = 0) -> dict:
        """
        Implements the correct 3-step Gladia V2 process:
        1. Upload file to get audio_url.
        2. Request transcription with audio_url to get result_url.
        3. Poll result_url until the job is done.
        """
        if not self.api_key:
            logger.error("Gladia API key is not configured.")
            raise ValueError("Gladia API key is missing.")

        headers = {"x-gladia-key": self.api_key}
        start_time = time.time()
        success = False

        try:
            async with httpx.AsyncClient() as client:
                
                # --- STEP 1: Upload the audio file (multipart/form-data) ---
                logger.info(f"Step 1/3: Uploading {audio_file_path} to Gladia...")
                mime_type, _ = mimetypes.guess_type(audio_file_path)
                with open(audio_file_path, "rb") as f:
                    files = {"audio": (audio_file_path, f, mime_type or "audio/wav")}
                    upload_response = await client.post(
                        f"{self.base_url}/upload", headers=headers, files=files, timeout=120.0
                    )
                upload_response.raise_for_status()
                audio_url = upload_response.json().get("audio_url")
                if not audio_url:
                    raise Exception("Gladia V2 did not return an audio_url.")
                logger.info(f"Step 1/3: Upload successful. Audio URL: {audio_url}")

                # --- STEP 2: Request transcription with diarization (application/json) ---
                logger.info("Step 2/3: Requesting transcription with diarization...")
                payload = {
                    "audio_url": audio_url,
                    "diarization": True,
                    "diarization_config": {
                        "min_speakers": min(num_room_participants, 2) if num_room_participants > 0 else 2,
                        "max_speakers": num_room_participants + 2 if num_room_participants > 0 else 4,
                    },
                }
                transcribe_response = await client.post(
                    f"{self.base_url}/pre-recorded", headers=headers, json=payload, timeout=60.0
                )
                transcribe_response.raise_for_status()
                result_url = transcribe_response.json().get("result_url")
                if not result_url:
                    raise Exception("Gladia V2 did not return a result_url.")
                logger.info(f"Step 2/3: Transcription started. Polling URL: {result_url}")

                # --- STEP 3: Poll for results ---
                MAX_POLL_SECONDS = 300
                MAX_POLL_ITERATIONS = 100
                poll_start = time.time()
                iteration = 0
                
                while True:
                    iteration += 1
                    elapsed = time.time() - poll_start
                    
                    if elapsed > MAX_POLL_SECONDS:
                        raise Exception(f"Gladia timeout: {elapsed:.0f}s exceeded {MAX_POLL_SECONDS}s limit")
                    if iteration > MAX_POLL_ITERATIONS:
                        raise Exception(f"Gladia timeout: {iteration} iterations exceeded limit")
                    
                    await asyncio.sleep(5)
                    logger.info(f"Step 3/3: Polling for results (iteration {iteration}, elapsed {elapsed:.1f}s)...")
                    
                    poll_response = await client.get(result_url, headers=headers, timeout=60.0)
                    poll_response.raise_for_status()
                    
                    data = poll_response.json()
                    status = data.get("status")
                    
                    if status == "done":
                        logger.info(f"Step 3/3: Transcription complete! ({elapsed:.1f}s total)")
                        success = True
                        return self._format_result(data)
                    elif status == "error":
                        error_detail = data.get('error', 'Unknown error')
                        raise Exception(f"Gladia processing failed: {error_detail}")
                    else:
                        logger.info(f"Gladia job status: {status}. Waiting...")

        except httpx.HTTPStatusError as e:
            logger.error(f"Gladia API request failed: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Gladia processing: {e}")
            raise
        finally:
            await track_gladia_call(time.time() - start_time, success)

    def _format_result(self, gladia_result: dict) -> dict:
        """
        Formats the Gladia V2 API response into the structure our system expects.
        """
        # Debug: log raw response structure
        logger.info(f"Gladia raw result keys: {list(gladia_result.keys())}")
        result = gladia_result.get("result", {})
        logger.info(f"Gladia result keys: {list(result.keys())}")
        
        transcription = result.get("transcription", {})
        if not transcription:
            logger.warning(f"No transcription found in Gladia result. Full result: {result}")
            return {"full_text": "", "segments": []}

        full_text = transcription.get("full_transcript", "")
        utterances = transcription.get("utterances", [])
        logger.info(f"Gladia returned {len(utterances)} utterances")
        
        segments = []
        for utterance in utterances:
            segments.append({
                "speaker": f"Speaker {utterance.get('speaker', 'Unknown')}",
                "text": utterance.get("text", ""),
                "start": utterance.get("start", 0.0),
                "end": utterance.get("end", 0.0),
            })

        return {
            "full_text": full_text,
            "segments": segments
        }
gladia_service = GladiaService()
