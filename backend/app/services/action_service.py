import httpx
import logging
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc
from sqlalchemy.future import select
from datetime import datetime, timedelta

from app.models.action import Action, Assignment, ActionSuggestion, SuggestionStatus, ActionStatus
from app.models.pv import PV
from app.models.transcription import Transcription
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

class ActionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_action_patterns(self, limit: int = 5, target_language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Aggregates pending actions by title to identify patterns, with optional translation."""
        stmt = (
            select(Action.title, func.count(Action.id).label("count"))
            .where(Action.status == ActionStatus.PENDING)
            .group_by(Action.title)
            .order_by(desc("count"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        patterns = [{"title": row[0], "count": row[1]} for row in result.all()]
        
        if target_language and patterns:
            titles = [p["title"] for p in patterns]
            translated_titles = await self.translate_texts(titles, target_language)
            for i, p in enumerate(patterns):
                p["title"] = translated_titles[i] if i < len(translated_titles) else p["title"]
        
        return patterns

    async def get_recurring_statistics(self, target_language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Calculates ML suggestion statistics per assignee, with optional translation."""
        stmt = (
            select(
                ActionSuggestion.suggested_assignee,
                func.count(ActionSuggestion.id).label("total"),
                func.count(ActionSuggestion.id).filter(ActionSuggestion.status == SuggestionStatus.ACCEPTED).label("accepted"),
                func.count(ActionSuggestion.id).filter(ActionSuggestion.status == SuggestionStatus.REJECTED).label("rejected")
            )
            .group_by(ActionSuggestion.suggested_assignee)
        )
        result = await self.db.execute(stmt)
        
        stats = []
        for row in result.all():
            assignee = row[0] if row[0] else "Unassigned"
            stats.append({
                "suggested_assignee": assignee,
                "total_suggestions": row[1],
                "accepted_count": row[2],
                "rejected_count": row[3]
            })

        if target_language and stats:
            assignees = [s["suggested_assignee"] for s in stats]
            translated_assignees = await self.translate_texts(assignees, target_language)
            for i, s in enumerate(stats):
                s["suggested_assignee"] = translated_assignees[i] if i < len(translated_assignees) else s["suggested_assignee"]
                
        return stats

    async def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        """Generic method to translate a list of strings using Mistral."""
        if not texts or not target_language:
            return texts
            
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        
        lang_names = {"ar": "Arabic", "fr": "French", "en": "English"}
        target_lang = lang_names.get(target_language.split('-')[0], "French")

        system_content = f"You are a professional translator. Translate the following list of strings into {target_lang}. Return ONLY a JSON array of strings in the exact same order."
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": json.dumps(texts)}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                content_str = result["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                return parsed if isinstance(parsed, list) else list(parsed.values())[0]
        except Exception as e:
            logger.error(f"Failed to translate texts: {e}")
            return texts

    async def generate_suggestions_from_transcription(self, meeting_id: str) -> List[ActionSuggestion]:
        """Analyzes transcription to suggest new actions."""
        # 1. Fetch Transcription
        stmt = select(Transcription).where(Transcription.meeting_id == meeting_id)
        res = await self.db.execute(stmt)
        transcription = res.scalar_one_or_none()
        
        if not transcription or not transcription.full_text:
            logger.warning(f"No transcription found for meeting {meeting_id}")
            return []

        # 2. Call Mistral
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        
        system_content = """You are an AI assistant that analyzes meeting transcripts to identify potential action items, tasks, or follow-ups that were discussed but might not have been formally decided yet.
Extract these implicit suggestions.
Return ONLY a JSON array of objects with the following structure:
[
  {
    "title": "Short title of the task",
    "description": "More detailed description",
    "suggested_assignee": "Name of the person if mentioned, else null",
    "confidence_score": 0.0 to 1.0 indicating how likely this is a real task
  }
]"""

        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Analyze this transcript:\n\n{transcription.full_text}"}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
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
                
                # Check if it returned a dict wrapper around the array (common with Mistral json mode)
                parsed = json.loads(content_str)
                suggestions_data = parsed if isinstance(parsed, list) else list(parsed.values())[0]
                
                if not isinstance(suggestions_data, list):
                    logger.error("Mistral returned invalid format for suggestions")
                    return []

        except Exception as e:
            logger.error(f"Failed to generate suggestions via Mistral: {e}")
            return []

        # 3. Store in DB
        suggestions = []
        for item in suggestions_data:
            suggestion = ActionSuggestion(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                title=item.get("title", "Unknown Task"),
                description=item.get("description", ""),
                suggested_assignee=item.get("suggested_assignee"),
                confidence_score=item.get("confidence_score", 0.5),
                status="suggested"
            )
            self.db.add(suggestion)
            suggestions.append(suggestion)
            
        await self.db.commit()
        return suggestions

    async def extract_actions_from_pv(
        self, pv_id: str, actions_data: List[dict]
    ) -> List[Action]:
        """n8n-Callback von Mistral verarbeiten"""
        # Lookup meeting_id from PV
        pv_res = await self.db.execute(select(PV).where(PV.id == pv_id))
        pv = pv_res.scalar_one_or_none()
        if not pv:
            logger.error(f"PV {pv_id} not found. Cannot extract actions.")
            return []

        meeting_id = pv.meeting_id
        new_actions = []

        for item in actions_data:
            action_id = str(uuid.uuid4())
            action = Action(
                id=action_id,
                meeting_id=meeting_id,
                title=item.get("title", "Untitled Action"),
                description=item.get("description", ""),
                due_date=(
                    datetime.fromisoformat(item["due_date"])
                    if item.get("due_date")
                    else None
                ),
                status="pending",
            )
            self.db.add(action)
            new_actions.append(action)

            assignee_id = item.get("assignee_id")
            if assignee_id:
                assignment = Assignment(
                    id=str(uuid.uuid4()), action_id=action_id, user_id=assignee_id
                )
                self.db.add(assignment)

        await self.db.commit()

        # Trigger notifications for each assigned action
        for action in new_actions:
            if action.assignments and action.assignments[0].user_id:
                await self.assign_action(
                    str(action.id), str(action.assignments[0].user_id)
                )

        return new_actions

    async def assign_action(self, action_id: str, user_id: str) -> Optional[Action]:
        """Verantwortlichen zuweisen -> WhatsApp Reminder via n8n"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            return None

        # Check if assignment already exists
        assignment_result = await self.db.execute(
            select(Assignment).where(
                Assignment.action_id == action_id, Assignment.user_id == user_id
            )
        )
        existing_assignment = assignment_result.scalar_one_or_none()

        if not existing_assignment:
            assignment = Assignment(
                id=str(uuid.uuid4()), action_id=action_id, user_id=user_id
            )
            self.db.add(assignment)
            await self.db.commit()

        # WhatsApp Reminder via n8n
        payload = {
            "event": "action.assigned",
            "action_id": action.id,
            "title": str(action.title),
            "assignee_id": user_id,
            "due_date": action.due_date.isoformat() if action.due_date else None,
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
                logger.info(f"n8n notification triggered for action {action_id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n notification: {e}")

        return action

    async def update_action_status(
        self, action_id: str, status: str
    ) -> Optional[Action]:
        """Status-Änderung -> n8n Notification"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            return None

        # Hack for enum
        action.status = status  # type: ignore
        await self.db.commit()

        # n8n Notification (e.g., to Manager)
        payload = {
            "event": "action.status_updated",
            "action_id": action.id,
            "status": status,
            "title": str(action.title),
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to trigger n8n status notification: {e}")

        return action

    async def learn_from_feedback(self, suggestion_id: str, action: str) -> None:
        """Records feedback and creates a real Action if accepted."""
        stmt = select(ActionSuggestion).where(ActionSuggestion.id == suggestion_id)
        res = await self.db.execute(stmt)
        suggestion = res.scalar_one_or_none()

        if not suggestion:
            logger.warning(f"Suggestion {suggestion_id} not found for feedback.")
            return

        if action == "accept":
            suggestion.status = "accepted"
            # Create the actual action entry so it appears in the PV/PDF
            new_action = Action(
                id=str(uuid.uuid4()),
                meeting_id=suggestion.meeting_id,
                title=suggestion.title,
                description=suggestion.description,
                status="pending",
                priority="medium"
            )
            self.db.add(new_action)
            logger.info(f"Suggestion {suggestion_id} accepted and converted to Action {new_action.id}")
        elif action == "reject":
            suggestion.status = "rejected"
        
        await self.db.commit()

    async def translate_suggestions(self, suggestions_data: List[dict], target_language: str) -> List[dict]:
        """Translates a list of suggestions for the UI sidebar using Mistral."""
        if not suggestions_data:
            return []
            
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        
        lang_names = {"ar": "Arabic", "fr": "French", "en": "English"}
        target_lang = lang_names.get(target_language, "French")

        system_content = f"You are a professional translator. Translate the following list of action suggestions into {target_lang}. Return ONLY a JSON array of objects with 'id', 'title', and 'description'."
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": json.dumps(suggestions_data)}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                content_str = result["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                # Handle Mistral's potential dict wrapper
                return parsed if isinstance(parsed, list) else list(parsed.values())[0]
        except Exception as e:
            logger.error(f"Failed to translate suggestions: {e}")
            return suggestions_data

    async def get_due_actions(self) -> List[Action]:
        """Für tägliche Reminder (via Celery)"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        result = await self.db.execute(
            select(Action).where(
                Action.due_date <= tomorrow, Action.status != "completed"
            )
        )
        return list(result.scalars().all())

    async def escalate_overdue(self, action_id: str) -> None:
        """Eskalation an Manager"""
        payload = {"event": "action.escalate", "action_id": action_id}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to trigger n8n escalate notification: {e}")
