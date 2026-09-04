import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MistralFusionService:
    """
    Phase 5: Mistral Fusion-Prompt Service.
    Combines audio-based matching confidence with text context to resolve
    "Speaker 0" → Name mappings using Mistral LLM.
    """

    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.base_url = "https://api.mistral.ai/v1"
        self.model = "ministral-8b-latest"

    async def fuse_speaker_mapping(
        self,
        speaker_label: str,
        text_context: str,
        audio_matches: List[Dict],
        client_id: str,
        candidates: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float, str]:
        """
        Fuse audio matching results with text context to determine the most likely speaker name.

        Args:
            speaker_label: Gladia speaker label (e.g., "Speaker 0")
            text_context: Transcript text associated with this speaker
            audio_matches: List of audio matching results:
                [{"name": "Ahmed", "distance": 0.15, "confidence": "high"}, ...]
            client_id: Tenant ID for audit/context
            candidates: List of valid candidate names (participants + enrolled profiles).
                If provided, Mistral must choose from this list.

        Returns:
            (resolved_name, confidence_score, method)
            method: "audio", "text_inference", or "fusion"
        """
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY not set — falling back to audio-only matching")
            return self._fallback_to_audio(audio_matches)

        if not audio_matches and not text_context.strip():
            return None, 0.0, "no_match"

        if not audio_matches:
            return await self._text_only_inference(speaker_label, text_context, client_id, candidates)

        if not text_context.strip():
            return self._fallback_to_audio(audio_matches)

        try:
            prompt = self._build_fusion_prompt(speaker_label, text_context, audio_matches, candidates)
            response = await self._call_mistral(prompt)

            if response:
                parsed = self._parse_fusion_response(response)
                if parsed:
                    # Validate: name must be in candidates list if provided
                    if candidates and parsed["name"] not in candidates:
                        logger.warning(
                            f"Mistral returned name '{parsed['name']}' not in candidates. "
                            f"Rejecting as hallucination."
                        )
                        return self._fallback_to_audio(audio_matches)

                    logger.info(
                        f"Fusion result for {speaker_label}: {parsed['name']} "
                        f"(confidence={parsed['confidence']}, method=fusion)"
                    )
                    return parsed["name"], parsed["confidence"], "fusion"

            logger.warning("Fusion failed — falling back to audio matching")
            return self._fallback_to_audio(audio_matches)

        except Exception as e:
            logger.error(f"Mistral fusion failed: {e}")
            return self._fallback_to_audio(audio_matches)

    def _build_fusion_prompt(
        self,
        speaker_label: str,
        text_context: str,
        audio_matches: List[Dict],
        candidates: Optional[List[str]] = None,
    ) -> str:
        """Build the fusion prompt for Mistral."""
        audio_context = "\n".join(
            [
                f"- {m['name']} (distance: {m['distance']:.3f}, confidence: {m['confidence']})"
                for m in audio_matches[:5]
            ]
        )

        candidate_context = ""
        if candidates:
            # Limit to 20 candidates to avoid token limits
            limited = candidates[:20]
            candidate_context = f"\n- Valid participant names (choose ONLY from this list):\n"
            candidate_context += "\n".join([f"  - {c}" for c in limited])
            if len(candidates) > 20:
                candidate_context += f"\n  - ... and {len(candidates) - 20} more"

        prompt = f"""You are an AI assistant that resolves speaker identities in meeting transcripts.

Given:
- Speaker label from transcription: "{speaker_label}"
- Audio-based matching results (cosine distance against enrolled speaker profiles):
{audio_context}
{candidate_context}

- Transcript text spoken by this speaker:
{text_context[:1000]}

Task:
Determine the most likely real name for "{speaker_label}".

Rules:
1. If audio matching shows high confidence (<0.30 distance), prefer the audio result.
2. If audio matching is ambiguous or low confidence, use text context clues
   (e.g., self-introductions, others addressing the speaker by name, role context).
3. If a candidate list is provided, you MUST choose ONLY from that list.
4. If none of the candidates match, return null for the name.
5. NEVER invent or hallucinate names that are not in the candidate list.
6. Return ONLY a JSON object with this structure:
{{
  "name": "<resolved name from candidate list or null if unknown>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<brief explanation>"
}}

Do NOT include any text outside the JSON object."""

        return prompt

    async def _call_mistral(self, prompt: str) -> Optional[str]:
        """Call Mistral API with the fusion prompt, with retry logic for 429."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that outputs ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 256,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=15.0,
                    )
                    if response.status_code == 429:
                        wait_time = min(2 ** attempt * 5, 60)
                        retry_after = response.headers.get("retry-after")
                        if retry_after:
                            wait_time = int(retry_after)
                        logger.warning(
                            f"Mistral rate limited (429), retrying in {wait_time}s "
                            f"(attempt {attempt+1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = min(2 ** attempt * 5, 60)
                    logger.warning(f"Mistral rate limited, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise
            except Exception:
                raise

        logger.error(f"Mistral call failed after {max_retries} retries (rate limited)")
        return None

    def _parse_fusion_response(self, content: str) -> Optional[Dict]:
        """Parse the fusion response from Mistral."""
        try:
            parsed = json.loads(content)
            name = parsed.get("name")
            confidence = float(parsed.get("confidence", 0.0))

            if name and 0.0 <= confidence <= 1.0:
                return {"name": name, "confidence": confidence}

            return None
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse fusion response: {e}")
            return None

    async def _text_only_inference(
        self,
        speaker_label: str,
        text_context: str,
        client_id: str,
        candidates: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float, str]:
        """Infer speaker name from text context only (no audio matches)."""
        try:
            candidate_context = ""
            if candidates:
                limited = candidates[:20]
                candidate_context = f"\nValid participant names (choose ONLY from this list):\n"
                candidate_context += "\n".join([f"- {c}" for c in limited])

            prompt = f"""You are an AI assistant that identifies speakers from meeting transcripts.

Speaker label: "{speaker_label}"
Transcript text:
{text_context[:1000]}
{candidate_context}

Task:
Can you determine the real name of this speaker from the text context?
CRITICAL: Only return a name if there is an EXPLICIT self-introduction like:
- "I am [name]" / "My name is [name]" / "Ich bin [name]" / "أنا [name]"
- "This is [name] speaking"

Do NOT guess from:
- Names mentioned in passing
- Names of other people being discussed
- Titles, roles, or organizations
- Ambiguous references

If a candidate list is provided, you MUST choose ONLY from that list.
If there is no clear self-introduction, return name as null.

Return ONLY a JSON object:
{{
  "name": "<name from candidate list or null if unknown>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<brief explanation>"
}}"""

            response = await self._call_mistral(prompt)
            if response:
                parsed = self._parse_fusion_response(response)
                if parsed:
                    # Validate: name must be in candidates list if provided
                    if candidates and parsed["name"] not in candidates:
                        logger.warning(
                            f"Text inference returned '{parsed['name']}' not in candidates. Rejecting."
                        )
                        return None, 0.0, "no_match"

                    logger.info(f"Text inference for {speaker_label}: {parsed['name']}")
                    return parsed["name"], parsed["confidence"], "text_inference"

            return None, 0.0, "no_match"

        except Exception as e:
            logger.error(f"Text-only inference failed: {e}")
            return None, 0.0, "no_match"

    def _fallback_to_audio(
        self,
        audio_matches: List[Dict],
    ) -> Tuple[Optional[str], float, str]:
        """Fallback to best audio match when fusion fails."""
        if not audio_matches:
            return None, 0.0, "no_match"

        best = min(audio_matches, key=lambda m: m["distance"])

        if best["confidence"] == "high":
            confidence_score = 0.9
        elif best["confidence"] == "medium":
            confidence_score = 0.7
        elif best["confidence"] == "low":
            confidence_score = 0.4
        else:
            return None, 0.0, "no_match"

        return best["name"], confidence_score, "audio"


mistral_fusion_service = MistralFusionService()
