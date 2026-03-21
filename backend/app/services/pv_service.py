import httpx
import logging
import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.config import settings
from app.models.pv import PV

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Custom exception for translation failures."""
    pass


class PVService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    async def generate_pv(transcription_text: str, target_language: str = "fr") -> Dict[str, Any]:
        """
        Generates a Procès-Verbal (PV) from transcription text using Mistral.
        Supports Arabic (ar), French (fr), English (en).
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            }
            
            lang_names = {
                "ar": "Arabic (العربية)",
                "fr": "French (Français)",
                "en": "English"
            }
            target_lang_name = lang_names.get(target_language, "French (Français)")

            system_content = f"""You are a professional secretary creating a 'Procès-Verbal' (PV) from meeting transcriptions.
Analyze the provided text and create a structured summary.
CRITICAL: All content (titles, summaries, descriptions) MUST be written in {target_lang_name}.
The JSON keys MUST remain exactly as follows:

{{
  "title": "Meeting Title",
  "summary": "Detailed summary of discussions",
  "decisions": ["Decision 1", "Decision 2"],
  "actions": [
    {{
      "description": "Task description",
      "priority": "high/medium/low",
      "priority_reason": "Short justification",
      "assignee": "Responsible person",
      "deadline": "YYYY-MM-DD or null"
    }}
  ]
}}

Answer only in valid JSON format."""

            payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": f"""Create a PV for the following transcription in {target_lang_name}:

{transcription_text}""",
                    },
                ],
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()
                content_str = result["choices"][0]["message"]["content"]
                
                try:
                    parsed_content = json.loads(content_str)
                    if isinstance(parsed_content, dict):
                        return parsed_content
                    else:
                        logger.warning(f"Mistral API (generate_pv) returned a non-dictionary: {parsed_content}")
                        return {"title": "PV Generation Failed", "summary": content_str, "decisions": [], "actions": []}
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from Mistral API (generate_pv): {content_str}")
                    return {"title": "PV Generation Error", "summary": "Could not parse AI response.", "decisions": [], "actions": []}

        except Exception as e:
            logger.error(f"PV generation error: {e}")
            raise RuntimeError(f"Mistral API error during PV generation: {e}")

    @staticmethod
    async def translate_content(content_dict: Dict[str, Any], target_language: str) -> Dict[str, Any]:
        """
        Translates existing PV content into a target language using Mistral.
        This is used for multilingual exports when the requested language differs from stored data.
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            }

            lang_names = {
                "ar": "Arabic (العربية)",
                "fr": "French (Français)",
                "en": "English"
            }
            target_lang_name = lang_names.get(target_language, "French (Français)")

            system_content = f"""You are a professional translator. 
Translate the provided meeting minutes JSON into {target_lang_name}.
KEEP the exact same JSON structure and keys. 
ONLY translate the values (text strings)."""

            payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": f"""Translate this JSON to {target_lang_name}:

{json.dumps(content_dict)}""",
                    },
                ],
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                content_str = result["choices"][0]["message"]["content"]
                
                try:
                    parsed_content = json.loads(content_str)
                    if isinstance(parsed_content, dict):
                        return parsed_content
                    else:
                        logger.warning(f"Mistral AI (translate) returned a non-dictionary: {parsed_content}")
                        raise TranslationError("Mistral AI returned a non-dictionary object.")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON from Mistral API (translate): {content_str}")
                    raise TranslationError(f"Failed to decode JSON response from AI: {e}")

        except Exception as e:
            logger.error(f"Translation API error: {e}")
            raise TranslationError(f"An error occurred during translation: {e}")

    async def validate_pv(self, pv_id: str, user_id: str, client_id: str) -> Optional[PV]:
        """Marks a PV as validated by a specific user."""
        stmt = select(PV).where(PV.id == pv_id).where(PV.client_id == client_id)
        result = await self.db.execute(stmt)
        pv = result.scalar_one_or_none()

        if not pv:
            return None

        pv.is_validated = True
        pv.validated_by_id = user_id
        pv.validated_at = datetime.utcnow()
        pv.status = "published"

        await self.db.commit()
        await self.db.refresh(pv)

        await self._notify_validation(pv)

        return pv

    async def _notify_validation(self, pv: PV):
        payload = {"event": "pv.validated", "pv_id": pv.id, "meeting_id": pv.meeting_id}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    settings.N8N_WEBHOOK_PV_VALIDATED, json=payload, timeout=5.0
                )
        except Exception as e:
            logger.error(f"Failed to notify n8n about PV validation: {e}")
