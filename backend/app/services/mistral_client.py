import httpx
import logging
from typing import Dict, Any, Optional, List
import json # Import json

from tenacity import retry, stop_after_attempt, wait_fixed, \
    retry_if_exception_type, before_sleep_log, retry_if_exception

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

MOCK_PV_RESPONSE = "" # This is a placeholder for testing purposes

class MistralClient:
    def __init__(self):
        self.api_base_url = settings.MISTRAL_API_URL
        self.api_key = settings.MISTRAL_API_KEY
        self.client = httpx.AsyncClient(base_url=self.api_base_url)
        logger.info(f"MistralClient self.client type: {type(self.client)}")
        logger.info(f"MistralClient self.client.post type: {type(self.client.post)}")

    @retry(
        stop=stop_after_attempt(settings.MISTRAL_API_MAX_RETRIES),
        wait=wait_fixed(settings.MISTRAL_API_RETRY_DELAY),
        retry=retry_if_exception_type(httpx.RequestError) | retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def call_mistral_api(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = await self.client.post(endpoint, json=payload, headers=headers, timeout=settings.MISTRAL_API_TIMEOUT)
            response.raise_for_status()
            return await response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"Mistral API rate limit hit (429). Retrying...")
            else:
                logger.error(f"Mistral API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Mistral API request error: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise

    def _generate_prompt(self, template_name: str, **kwargs) -> str:
        templates = {
            "pv_generation": """
            Generate a "Protokollvermerk" (PV) from the following meeting transcription.
            The PV should summarize the key discussions, decisions, and action items.
            Transcription: {transcription}
            """,
            "extract_decisions": """
            From the following meeting transcription, extract all explicit decisions made.
            List each decision clearly, one per line.
            Transcription: {transcription}
            """,
            "extract_action_items": """
            From the following meeting transcription, extract all action items, including
            who is responsible and the deadline if mentioned. List each action item clearly, one per line.
            Transcription: {transcription}
            """,
            "summarize_meeting": """
            Provide a concise summary of the following meeting transcription.
            Focus on the main topics and outcomes.
            Transcription: {transcription}
            """,
            "structured_pv_generation": """
            Generate a structured "Protokollvermerk" (PV) from the following meeting transcription.
            The output MUST be a JSON object with the following keys:
            - "content": A comprehensive summary of the meeting.
            - "decisions": A list of explicit decisions made during the meeting.
            - "actions": A list of action items, including who is responsible and the deadline if mentioned.

            Example JSON output:
            {{
                "content": "Summary of the meeting...",
                "decisions": ["Decision 1", "Decision 2"],
                "actions": ["Action 1 (Responsible: John, Deadline: 2023-12-31)", "Action 2 (Responsible: Jane)"]
            }}

            Transcription: {transcription}
            """
        }
        template = templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown prompt template: {template_name}")
        return template.format(**kwargs)

    async def generate_pv(self, transcription: str) -> Optional[Dict[str, Any]]:
        prompt = self._generate_prompt("structured_pv_generation", transcription=transcription)
        payload = {
            "model": settings.MISTRAL_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.MISTRAL_TEMPERATURE,
            "max_tokens": settings.MISTRAL_MAX_TOKENS,
            "response_format": {"type": "json_object"} # Request JSON output
        }
        try:
            response = await self.call_mistral_api("/v1/chat/completions", payload)
            # Ensure the response content is parsed as JSON
            pv_data = json.loads(response["choices"][0]["message"]["content"].strip())
            return pv_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Mistral API for PV generation: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate structured PV: {e}")
            return None

    async def extract_decisions(self, transcription: str) -> Optional[List[str]]:
        prompt = self._generate_prompt("extract_decisions", transcription=transcription)
        payload = {
            "model": settings.MISTRAL_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.MISTRAL_TEMPERATURE,
            "max_tokens": settings.MISTRAL_MAX_TOKENS,
        }
        try:
            response = await self.call_mistral_api("/v1/chat/completions", payload)
            # Split by newline to get a list of decisions
            decisions_str = response["choices"][0]["message"]["content"].strip()
            return [d.strip() for d in decisions_str.split('\n') if d.strip()]
        except Exception as e:
            logger.error(f"Failed to extract decisions: {e}")
            return None

    async def extract_action_items(self, transcription: str) -> Optional[List[str]]:
        prompt = self._generate_prompt("extract_action_items", transcription=transcription)
        payload = {
            "model": settings.MISTRAL_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.MISTRAL_TEMPERATURE,
            "max_tokens": settings.MISTRAL_MAX_TOKENS,
        }
        try:
            response = await self.call_mistral_api("/v1/chat/completions", payload)
            # Split by newline to get a list of action items
            actions_str = response["choices"][0]["message"]["content"].strip()
            return [a.strip() for a in actions_str.split('\n') if a.strip()]
        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return None

    async def summarize_meeting(self, transcription: str) -> Optional[str]:
        prompt = self._generate_prompt("summarize_meeting", transcription=transcription)
        payload = {
            "model": settings.MISTRAL_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.MISTRAL_TEMPERATURE,
            "max_tokens": settings.MISTRAL_MAX_TOKENS,
        }
        try:
            response = await self.call_mistral_api("/v1/chat/completions", payload)
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Failed to summarize meeting: {e}")
            return None

mistral_client = MistralClient()