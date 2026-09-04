import httpx
import logging
import json
import asyncio
import time
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.config import settings
from app.models.pv import PV
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Concurrency limiter: max 2 parallel Mistral API calls
_mistral_semaphore = asyncio.Semaphore(2)

REQUIRED_PV_KEYS = {"title", "summary", "decisions", "actions"}

def _validate_pv_schema(data: dict) -> dict:
    """Validate and fix PV schema from Mistral response."""
    missing = REQUIRED_PV_KEYS - set(data.keys())
    if missing:
        logger.warning(f"PV missing keys: {missing}")
        for key in missing:
            data[key] = [] if key in ("decisions", "actions") else ""

    for i, action in enumerate(data.get("actions", [])):
        if not isinstance(action, dict) or "description" not in action:
            logger.warning(f"Action {i} missing description, skipping")
            data["actions"][i] = None
    data["actions"] = [a for a in data.get("actions", []) if a is not None]

    return data

async def track_mistral_call(latency: float, success: bool):
    try:
        r = await get_redis_client()
        await r.incr("ai:mistral:calls")
        if not success:
            await r.incr("ai:mistral:errors")
        if latency > 0:
            await r.lpush("ai:mistral:latencies", latency)
            await r.ltrim("ai:mistral:latencies", 0, 99)
    except Exception as e:
        logger.error(f"Failed to track Mistral metrics: {e}")

class TranslationError(Exception):
    """Custom exception for translation failures."""
    pass


class PVService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    async def generate_pv(
        sentinel_summary: str,
        full_transcript: str,
        target_language: str = "fr",
        participant_names: Optional[List[str]] = None,
        speaker_mappings: Optional[List[Dict[str, Any]]] = None,
        speaker_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generates a Procès-Verbal (PV) from meeting transcription using Mistral.
        
        Dual-context approach:
        - sentinel_summary: Used for PV summary/decisions (compact, cost-efficient)
        - full_transcript: Used for action assignment (preserves "who said what")
        
        This mirrors Microsoft Teams Copilot: summary for overview, full transcript for task extraction.
        """
        start_time = time.time()
        success = False
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

            current_year = datetime.now().year
            
            participants_context = ""
            if participant_names:
                participants_context = f"The valid participants for this meeting are: {', '.join(participant_names)}."

            speaker_context = ""
            if speaker_mappings:
                speaker_lines = ["Identified speakers in this meeting:"]
                for m in speaker_mappings:
                    label = m.get("speaker_label", "Unknown")
                    name = m.get("resolved_name") or "Unknown"
                    conf = m.get("confidence", 0.0)
                    method = m.get("method", "unknown")
                    speaker_lines.append(
                        f"  {label} = {name} (confidence: {conf:.2f}, method: {method})"
                    )
                speaker_context = "\n".join(speaker_lines) + "\n"

                if speaker_segments:
                    name_map = {}
                    for m in speaker_mappings:
                        if m.get("resolved_name"):
                            name_map[m["speaker_label"]] = m["resolved_name"]
                    quote_lines = ["Key statements from the transcript:"]
                    seen = set()
                    for seg in speaker_segments:
                        raw_speaker = seg.get("speaker", "Unknown")
                        resolved = name_map.get(raw_speaker, raw_speaker)
                        text = seg.get("text", "").strip()
                        if text and len(text) > 15 and resolved not in seen:
                            truncated = text[:200]
                            if len(text) > 200:
                                truncated += "..."
                            quote_lines.append(f'  {resolved}: "{truncated}"')
                            seen.add(resolved)
                    if len(quote_lines) > 1:
                        speaker_context += "\n".join(quote_lines) + "\n"

            # Build explicit allowed names list for anti-hallucination
            allowed_names = []
            if participant_names:
                allowed_names.extend(participant_names)
            if speaker_mappings:
                for m in speaker_mappings:
                    name = m.get("resolved_name")
                    if name and name not in allowed_names:
                        allowed_names.append(name)
            allowed_names_str = ", ".join(allowed_names) if allowed_names else "None (return null for assignee)"

            system_content = f"""You are a professional secretary creating a 'Procès-Verbal' (PV) from meeting transcriptions.

MEETING DATE: {datetime.now().strftime('%Y-%m-%d')} (TODAY)
CRITICAL: All deadlines MUST be in the FUTURE (after {datetime.now().strftime('%Y-%m-%d')}). If someone says "next week", the deadline is approximately 7 days from today. If someone says "in two weeks", it is approximately 14 days from today. NEVER generate dates in the past.

CONTEXT PROVIDED:
1. MEETING SUMMARY (for overview):
{sentinel_summary}

2. FULL TRANSCRIPT (for understanding who said what):
{full_transcript}

{participants_context}
{speaker_context}

CRITICAL RULES FOR ASSIGNEE ASSIGNMENT:
1. CLOSED LIST: You may ONLY use the following names as assignees: [{allowed_names_str}]
2. EXACT MATCH: You MUST use the EXACT name as written above. No variants, no transliterations, no abbreviations.
3. NO INVENTION: NEVER invent names, NEVER use names not in the closed list.
4. SINGLE SPEAKER FALLBACK: If there is only one identified speaker and no other assignee is clearly mentioned, assign to that speaker.
5. INVALID NAMES: If no valid person from the closed list is clearly assigned to a task, assign to the single identified speaker.

Examples of INVALID assignees (NEVER use these):
- "Mohammed Al-Arabi Al-Nakdi" (variant of a valid name)
- "AbdulQader Rabteny" (invented name)
- "N/A", "null", "none", tool names, generic terms

The JSON keys MUST remain exactly as follows:

{{
  "title": "Meeting Title",
  "tags": "keyword1, keyword2, keyword3",
  "summary": "Detailed summary of discussions",
  "decisions": ["Decision 1", "Decision 2"],
  "actions": [
    {{
      "description": "Task description",
      "priority": "high/medium/low",
      "priority_reason": "Short justification",
      "assignee": "EXACT name from the closed list above",
      "deadline": "YYYY-MM-DD or null (Only return null if NO timeframe or date is mentioned. Current date: {datetime.now().strftime('%Y-%m-%d')}. ALL deadlines MUST be in the FUTURE. 'Next week' ≈ 7 days from now. 'In two weeks' ≈ 14 days from now.)"
    }}
  ]
}}

Answer only in valid JSON format."""

            # Build allowed names list for JSON schema constraint
            allowed_names_list = [n for n in allowed_names if n] if allowed_names else []
            schema_assignee_values = allowed_names_list + [None] if allowed_names_list else [None]

            payload = {
                "model": "mistral-medium-latest",
                "messages": [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": f"""Create a PV in {target_lang_name} based on the meeting summary and full transcript provided above.
Use the summary for the PV overview, and the full transcript to determine who is responsible for each task.""",
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            async with _mistral_semaphore:
                async with httpx.AsyncClient() as client:
                    max_retries = 3
                    result = None
                    for attempt in range(max_retries):
                        try:
                            response = await client.post(
                                "https://api.mistral.ai/v1/chat/completions",
                                headers=headers,
                                json=payload,
                                timeout=60.0,
                            )
                            if response.status_code == 429:
                                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                                logger.warning(f"Mistral 429 rate limited, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})")
                                await asyncio.sleep(retry_after)
                                continue
                            response.raise_for_status()
                            result = response.json()
                            break
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 429 and attempt < max_retries - 1:
                                retry_after = int(e.response.headers.get("Retry-After", 2 ** attempt))
                                logger.warning(f"Mistral 429, retry in {retry_after}s")
                                await asyncio.sleep(retry_after)
                                continue
                            raise
                if result is None:
                    raise RuntimeError("Mistral API returned no result after all retries (possible 429 rate limit)")
                content_str = result["choices"][0]["message"]["content"]
                
                # AUDIT LOGGING: Capture Mistral response for assignee audit
                logger.info(f"[MISTRAL_AUDIT] Raw response keys: {list(result.keys())}")
                logger.info(f"[MISTRAL_AUDIT] Usage: {result.get('usage', 'N/A')}")
                logger.info(f"[MISTRAL_AUDIT] Model: {result.get('model', 'N/A')}")
                
                try:
                    parsed_content = json.loads(content_str)
                    if isinstance(parsed_content, dict):
                        # AUDIT: Log extracted assignees
                        assignees = [a.get("assignee") for a in parsed_content.get("actions", []) if isinstance(a, dict)]
                        logger.info(f"[MISTRAL_AUDIT] Extracted assignees: {assignees}")
                        logger.info(f"[MISTRAL_AUDIT] Allowed names were: {allowed_names}")
                        logger.info(f"[MISTRAL_AUDIT] Participant names: {participant_names}")
                        logger.info(f"[MISTRAL_AUDIT] Speaker mappings: {speaker_mappings}")
                        
                        # VALIDATION: Check assignees against closed list
                        allowed_set = set(n.lower() for n in allowed_names if n)
                        invalid_assignees = []
                        for a in parsed_content.get("actions", []):
                            if isinstance(a, dict) and a.get("assignee"):
                                if a["assignee"].lower() not in allowed_set:
                                    invalid_assignees.append(a["assignee"])
                        
                        if invalid_assignees:
                            logger.warning(f"[MISTRAL_AUDIT] Invalid assignees detected: {invalid_assignees}")
                            logger.info(f"[MISTRAL_AUDIT] Allowed names: {allowed_names}")
                        
                        parsed_content = _validate_pv_schema(parsed_content)
                        success = True
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
        finally:
            await track_mistral_call(time.time() - start_time, success)

    @staticmethod
    async def translate_content(content_dict: Dict[str, Any], target_language: str) -> Dict[str, Any]:
        """
        Translates existing PV content into a target language using Mistral.
        This is used for multilingual exports when the requested language differs from stored data.
        """
        start_time = time.time()
        success = False
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
CRITICAL: KEEP the exact same JSON keys (e.g., "title", "summary", "decisions", "actions", "description", "assignee", "due_date"). 
ONLY translate the text values (strings). 
DO NOT translate the keys themselves. 
The output MUST be a valid JSON object with the identical structure as the input."""

            payload = {
                "model": "mistral-medium-latest",
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

            async with _mistral_semaphore:
                async with httpx.AsyncClient() as client:
                    max_retries = 3
                    result = None
                    for attempt in range(max_retries):
                        try:
                            response = await client.post(
                                "https://api.mistral.ai/v1/chat/completions",
                                headers=headers,
                                json=payload,
                                timeout=30.0,
                            )
                            if response.status_code == 429:
                                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                                logger.warning(f"Mistral 429 rate limited, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})")
                                await asyncio.sleep(retry_after)
                                continue
                            response.raise_for_status()
                            result = response.json()
                            break
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 429 and attempt < max_retries - 1:
                                retry_after = int(e.response.headers.get("Retry-After", 2 ** attempt))
                                logger.warning(f"Mistral 429, retry in {retry_after}s")
                                await asyncio.sleep(retry_after)
                                continue
                            raise
                if result is None:
                    raise RuntimeError("Mistral API returned no result after all retries (possible 429 rate limit)")
                content_str = result["choices"][0]["message"]["content"]
                
                try:
                    parsed_content = json.loads(content_str)
                    if isinstance(parsed_content, dict):
                        success = True
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
        finally:
            await track_mistral_call(time.time() - start_time, success)

    async def validate_pv(self, pv_id: str, user_id: str, client_id: str) -> Optional[PV]:
        """Marks a PV as validated by a specific user."""
        stmt = select(PV).where(PV.id == pv_id).where(PV.client_id == client_id)
        result = await self.db.execute(stmt)
        pv = result.scalar_one_or_none()

        if not pv:
            return None

        pv.is_validated = True
        pv.validated_by_id = user_id
        pv.validated_at = datetime.now(timezone.utc)
        pv.status = "published"

        await self.db.commit()
        await self.db.refresh(pv)

        await self._notify_validation(pv)

        return pv

    async def _notify_validation(self, pv: PV):
        payload = {"event": "pv.validated", "pv_id": pv.id, "meeting_id": pv.meeting_id, "client_id": pv.client_id}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    settings.N8N_WEBHOOK_PV_VALIDATED, json=payload, timeout=5.0
                )
        except Exception as e:
            logger.error(f"Failed to notify n8n about PV validation: {e}")
