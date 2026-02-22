import httpx
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class PVService:
    @staticmethod
    async def generate_pv(transcription_text: str) -> Dict[str, Any]:
        """
        Generates a Procès-Verbal (PV) from transcription text using the Mistral AI API.
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {
                        "role": "system",
                        "content": "Du erstellst professionelle Procès-Verbaux aus Meeting-Transkriptionen. Format: Einleitung, Diskussionspunkte, Entscheidungen, Action-Items. Antworte in einem strukturierten JSON Format."
                    },
                    {
                        "role": "user",
                        "content": f"Erstelle ein PV für folgende Transkription:\n\n{transcription_text}"
                    }
                ],
                "response_format": {"type": "json_object"}
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                result = response.json()
                # Extract content from the first choice
                content_str = result['choices'][0]['message']['content']
                import json
                return json.loads(content_str)
                
        except Exception as e:
            logger.error(f"PV generation error: {e}")
            # Return a fallback structure in case of error
            return {
                "title": "Automatisches Protokoll",
                "summary": "Fehler bei der automatischen Generierung.",
                "raw_transcription_preview": transcription_text[:200]
            }
