import httpx
import logging
from typing import Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

MOCK_PV_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": """
Meeting Title: Test Meeting for PV Generation
Date: 2026-02-16
Participants: Test User
Key Decisions:
- Decision 1: To proceed with the project.
Action Items:
- Action 1: Prepare the project plan (Assignee: Test User, Deadline: 2026-02-20)
Summary: The meeting discussed the project's initial phase and decided to move forward with a detailed plan.
"""
            }
        }
    ]
}

MOCK_DECISIONS_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": """
["Project Alpha will be launched next month.", "Allocate more budget to marketing."]
"""
            }
        }
    ]
}

MOCK_ACTION_POINTS_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": """
["Prepare the project plan (Assignee: Test User, Deadline: 2026-02-20)", "Follow up with the marketing team"]
"""
            }
        }
    ]
}

class MistralClient:
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.base_url = settings.MISTRAL_API_BASE_URL
        self.model = settings.MISTRAL_API_MODEL
        self.client = httpx.AsyncClient()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True
    )
    async def call_mistral_api(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> Optional[str]:
        if settings.MOCK_MISTRAL_API:
            logger.info(f"Using mock Mistral API response for prompt containing: {prompt[:100]}...")
            if "Extract all key decisions" in prompt:
                logger.info("Returning mock decisions response.")
                return MOCK_DECISIONS_RESPONSE["choices"][0]["message"]["content"]
            if "Extract all action points" in prompt:
                logger.info("Returning mock action points response.")
                return MOCK_ACTION_POINTS_RESPONSE["choices"][0]["message"]["content"]
            logger.info("Returning mock PV response.")
            return MOCK_PV_RESPONSE["choices"][0]["message"]["content"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = await self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.RequestError as e:
            logger.error(f"Mistral API request failed due to network or connection error: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Mistral API returned an HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except KeyError as e:
            logger.error(f"Mistral API response missing expected key: {e}. Response: {response.json()}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while calling Mistral API: {e}")
            return None

    def _generate_prompt(self, template_name: str, **kwargs) -> str:
        templates = {
            "pv_generation": """
            Generate a "Protokoll-Vorlage" (PV) from the following meeting transcription.
            The PV should include:
            - Meeting Title (if discernible)
            - Date (if discernible)
            - Participants (if discernible)
            - Key Decisions
            - Action Items (with assignee and deadline if possible)
            - Summary of discussion points

            Transcription:
            {transcription}
            """,
            "extract_decisions": """
            Extract all key decisions from the following meeting transcription.
            Return the decisions as a JSON array of strings.

            Transcription:
            {transcription}
            """,
            "extract_action_points": """
            Extract all action points from the following meeting transcription.
            For each action point, identify the assignee and deadline if mentioned.

            Transcription:
            {transcription}
            """,
            "generate_summary": """
            Generate a concise summary of the following meeting transcription.
            Focus on the main topics discussed and the overall outcome.

            Transcription:
            {transcription}
            """
        }
        template = templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown prompt template: {template_name}")
        return template.format(**kwargs)

    async def generate_pv(self, transcription: str) -> Optional[str]:
        prompt = self._generate_prompt("pv_generation", transcription=transcription)
        return await self.call_mistral_api(prompt)

    async def extract_decisions(self, transcription: str) -> Optional[str]:
        prompt = self._generate_prompt("extract_decisions", transcription=transcription)
        decisions_content = await self.call_mistral_api(prompt)
        if not decisions_content:
            return "[]"  # Return an empty JSON array if no decisions are extracted
        return decisions_content

    async def extract_action_points(self, transcription: str) -> Optional[str]:
        prompt = self._generate_prompt("extract_action_points", transcription=transcription)
        return await self.call_mistral_api(prompt)

    async def generate_summary(self, transcription: str) -> Optional[str]:
        prompt = self._generate_prompt("generate_summary", transcription=transcription)
        return await self.call_mistral_api(prompt)