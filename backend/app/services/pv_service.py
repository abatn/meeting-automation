import httpx
import logging
from typing import Dict, Any
from app.core.config import settings


logger = logging.getLogger(__name__)


class PVService:
    @staticmethod
    async def generate_pv(transcription_text: str) -> Dict[str, Any]:
        """
        Generates a Procès-Verbal (PV) from transcription text using Mistral.
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }
            system_content = """Du erstellst professionelle Procès-Verbaux (PV) aus
Meeting-Transkriptionen. Kontext: Maghreb/Tunesien (Sprachen: Arabisch,
Französisch, Englisch Mix/Code-Switching). Analysiere den Transkript
und erstelle eine strukturierte Zusammenfassung in FRANZÖSISCH oder ARABISCH.

Format: Einleitung, Diskussionspunkte, Entscheidungen, Action-Items.

Für JEDE Aufgabe (Action Item) bestimme:
1. PRIORITÄT (high/medium/low) basierend auf Dringlichkeit und Wichtigkeit.
2. BEGRÜNDUNG für die Priorität (kurz, 1 Satz, als 'priority_reason').
3. DEADLINE (im Format YYYY-MM-DD, falls erwähnt, sonst null).
4. VERANTWORTLICHER (Name oder Rolle, als 'assignee').

Antworte EXKLUSIV im strukturierten JSON Format."""

            payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {
                        "role": "system",
                        "content": system_content
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
            raise RuntimeError(f"Mistral API error during PV generation: {e}")
