import asyncio
import httpx
import logging
import uuid
import os
import tempfile
import boto3
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc, or_
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone

from app.models.action import Action, Assignment, ActionSuggestion, SuggestionStatus, ActionStatus
from app.models.pv import PV
from app.models.transcription import Transcription, Speaker
from app.models.recording import Recording
from app.models.user import User
from app.models.meeting import Meeting
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

class ActionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_suggestion_status(
        self, suggestion_id: str, action: str, client_id: str
    ) -> None:
        """
        Fast path: Update suggestion status immediately (~50ms).
        Used by the Celery background task pattern to provide instant UI feedback.
        """
        stmt = select(ActionSuggestion).where(
            ActionSuggestion.id == suggestion_id,
            ActionSuggestion.client_id == client_id,
        )
        result = await self.db.execute(stmt)
        suggestion = result.scalars().first()

        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found for client {client_id}")

        suggestion.status = SuggestionStatus.ACCEPTED if action == "accept" else SuggestionStatus.REJECTED
        await self.db.commit()

    async def get_action_patterns(self, client_id: str, limit: int = 5, target_language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Aggregates pending actions by title to identify patterns, with optional translation."""
        stmt = (
            select(Action.title, func.count(Action.id).label("count"))
            .where(Action.client_id == client_id)
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

    async def get_recurring_statistics(self, client_id: str, target_language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Calculates ML suggestion statistics per assignee, with optional translation."""
        stmt = (
            select(
                ActionSuggestion.suggested_assignee,
                func.count(ActionSuggestion.id).label("total"),
                func.count(ActionSuggestion.id).filter(ActionSuggestion.status == SuggestionStatus.ACCEPTED).label("accepted"),
                func.count(ActionSuggestion.id).filter(ActionSuggestion.status == SuggestionStatus.REJECTED).label("rejected")
            )
            .where(ActionSuggestion.client_id == client_id)
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
            "model": "mistral-medium-latest",
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

    async def generate_suggestions_from_transcription(self, meeting_id: str, client_id: str, target_language: str = "fr") -> List[ActionSuggestion]:
        """Analyzes transcription to suggest new actions in the specified language."""
        from sqlalchemy.orm import selectinload
        from app.models.meeting import Meeting
        from app.models.transcription import Speaker

        # 1. Fetch Transcription
        stmt = select(Transcription).where(Transcription.meeting_id == meeting_id).where(Transcription.client_id == client_id)
        res = await self.db.execute(stmt)
        transcription = res.scalar_one_or_none()
        
        if not transcription or not transcription.full_text:
            logger.warning(f"No transcription found for meeting {meeting_id}")
            return []

        # 2. Load speaker mappings for this meeting
        speaker_stmt = select(Speaker).where(Speaker.meeting_id == meeting_id)
        speaker_result = await self.db.execute(speaker_stmt)
        speakers = speaker_result.scalars().all()
        
        # Build name map: "Speaker 0" -> "Abdelkader Batnini"
        name_map = {}
        for s in speakers:
            resolved = s.resolved_name or s.name
            if resolved and s.name != resolved:
                name_map[s.name] = resolved
        
        # Apply name map to transcript
        enriched_text = transcription.full_text
        for label, name in name_map.items():
            enriched_text = enriched_text.replace(f"{label}:", f"{name}:")

        # 3. Load meeting with participants
        meeting_stmt = select(Meeting).options(selectinload(Meeting.participants)).where(Meeting.id == meeting_id)
        meeting_result = await self.db.execute(meeting_stmt)
        meeting = meeting_result.scalar_one_or_none()
        participant_names = [p.name for p in meeting.participants if p.name] if meeting else []

        # 4. Call Mistral with enriched context
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        
        lang_names = {"ar": "Arabic", "fr": "French", "en": "English"}
        language_name = lang_names.get(target_language, "French")

        allowed_names_str = ", ".join(participant_names) if participant_names else "any name mentioned in the transcript"

        system_content = f"""You are an AI assistant that analyzes meeting transcripts to identify potential action items, tasks, or follow-ups.
Extract these implicit suggestions.
CRITICAL: The 'title' and 'description' fields MUST be written in {language_name}.
CRITICAL RULES FOR ASSIGNEE ASSIGNMENT:
1. CLOSED LIST: You MUST assign EVERY action to a person from this list: [{allowed_names_str}]
2. NO NULL: NEVER return null, empty, "N/A", "TBD", or any placeholder for suggested_assignee.
3. NO INVENTION: NEVER invent names not in the closed list.
4. EXACT MATCH: Use the EXACT name as written in the closed list above.
5. SINGLE PERSON: If only one person is mentioned in the transcript, assign all actions to that person.
6. EVERY ACTION MUST HAVE AN ASSIGNEE: There is no such thing as an unassigned action.

Return ONLY a JSON array of objects with the following structure:
[
  {{
    "title": "Short title of the task in {language_name}",
    "description": "More detailed description in {language_name}",
    "suggested_assignee": "EXACT name from the closed list (NEVER null)",
    "confidence_score": 0.0 to 1.0 indicating how likely this is a real task
  }}
]"""

        payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Analyze this transcript and extract tasks in {language_name}:\n\n{enriched_text}"}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=45.0,
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

        # CRITICAL RULE: Validate and fix assignees — null/empty/invalid are FORBIDDEN
        INVALID_ASSIGNEES = {"n/a", "null", "none", "non défini", "undefined", "tbd", "tba", "gladia", "mistral", "sentinel", "ai", "assistant", ""}
        
        for item in suggestions_data:
            raw_assignee = item.get("suggested_assignee")
            
            if not raw_assignee or str(raw_assignee).strip().lower() in INVALID_ASSIGNEES:
                # Auto-resolve: find who spoke about this topic in the transcript
                assignee_name = None
                
                # Strategy 1: Search transcript for keywords matching the task
                task_text = f"{item.get('title', '')} {item.get('description', '')}".lower()
                task_words = {w for w in task_text.split() if len(w) > 3}
                
                if transcription.segments:
                    best_speaker = None
                    best_score = 0
                    for seg in transcription.segments:
                        seg_text = seg.get("text", "").lower()
                        seg_words = set(seg_text.split())
                        overlap = len(task_words & seg_words)
                        if overlap > best_score:
                            best_score = overlap
                            best_speaker = seg.get("speaker")
                    
                    if best_speaker and best_score >= 2:
                        # Check if it's a resolved name (not "Speaker 0")
                        if not best_speaker.startswith("Speaker "):
                            assignee_name = best_speaker
                        else:
                            # Map "Speaker 0" to resolved name
                            assignee_name = name_map.get(best_speaker)
                
                # Strategy 2: Single participant fallback
                if not assignee_name and len(participant_names) == 1:
                    assignee_name = participant_names[0]
                
                # Strategy 3: First participant fallback
                if not assignee_name and participant_names:
                    assignee_name = participant_names[0]
                
                item["suggested_assignee"] = assignee_name
                logger.warning(
                    f"[ASSIGNEE_FIX] Mistral returned invalid assignee '{raw_assignee}' — "
                    f"auto-resolved to '{assignee_name}' for task '{item.get('title')}'"
                )
            elif raw_assignee not in participant_names:
                # Validate against closed list — fix if not exact match
                matched = None
                for p in participant_names:
                    if p.lower() == str(raw_assignee).lower():
                        matched = p
                        break
                if matched:
                    item["suggested_assignee"] = matched
                else:
                    # Not in closed list — use first participant
                    item["suggested_assignee"] = participant_names[0] if participant_names else raw_assignee
                    logger.warning(
                        f"[ASSIGNEE_FIX] Mistral returned '{raw_assignee}' not in closed list — "
                        f"fallback to '{item['suggested_assignee']}'"
                    )

        suggestions = []
        for item in suggestions_data:
            suggestion = ActionSuggestion(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                client_id=client_id,
                title=item.get("title", "Unknown Task"),
                description=item.get("description", ""),
                suggested_assignee=item.get("suggested_assignee"),
                confidence_score=item.get("confidence_score", 0.8),
                status=SuggestionStatus.SUGGESTED,
                language=target_language
            )
            self.db.add(suggestion)
            suggestions.append(suggestion)
            
        await self.db.commit()
        return suggestions

    async def extract_actions_from_pv(
        self, pv_id: str, client_id: str, actions_data: List[dict]
    ) -> List[Action]:
        """n8n-Callback von Mistral verarbeiten"""
        # Lookup meeting_id from PV
        pv_res = await self.db.execute(select(PV).where(PV.id == pv_id).where(PV.client_id == client_id))
        pv = pv_res.scalar_one_or_none()
        if not pv:
            logger.error(f"PV {pv_id} not found for client {client_id}. Cannot extract actions.")
            return []

        meeting_id = pv.meeting_id
        new_actions = []

        for item in actions_data:
            action_id = str(uuid.uuid4())
            action = Action(
                id=action_id,
                client_id=client_id,
                meeting_id=meeting_id,
                title=item.get("title", "Untitled Action"),
                description=item.get("description", ""),
                due_date=(
                    datetime.fromisoformat(item["due_date"])
                    if item.get("due_date")
                    else None
                ),
                status=ActionStatus.PENDING,
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
                    str(action.id), str(action.assignments[0].user_id), client_id
                )

        return new_actions

    async def assign_action(self, action_id: str, user_id: str, client_id: str) -> Optional[Action]:
        """Verantwortlichen zuweisen -> WhatsApp Reminder via n8n"""
        result = await self.db.execute(select(Action).where(Action.id == action_id).where(Action.client_id == client_id))
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

        # TODO: n8n workflow for "action.assigned" not yet created.
        # Previously fired to base N8N_WEBHOOK_URL (no path) → 404.
        # Re-enable when n8n/workflows/action-assigned.json is deployed.
        # payload = {
        #     "event": "action.assigned",
        #     "action_id": action.id,
        #     "title": str(action.title),
        #     "assignee_id": user_id,
        #     "due_date": action.due_date.isoformat() if action.due_date else None,
        # }
        # try:
        #     async with httpx.AsyncClient() as client:
        #         await client.post(f"{settings.N8N_WEBHOOK_URL}/action-assigned", json=payload, timeout=5.0)
        #         logger.info(f"n8n notification triggered for action {action_id}")
        # except Exception as e:
        #     logger.error(f"Failed to trigger n8n notification: {e}")

        return action

    async def update_action_status(
        self, action_id: str, client_id: str, status: str
    ) -> Optional[Action]:
        """Status-Änderung -> n8n Notification"""
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Action)
            .where(Action.id == action_id)
            .where(Action.client_id == client_id)
            .options(selectinload(Action.assignments).selectinload(Assignment.user))
        )
        action = result.scalar_one_or_none()

        if not action:
            return None

        # Validate status against ActionStatus enum
        try:
            validated_status = ActionStatus(status)  # raises ValueError if not a member
        except ValueError:
            allowed = ", ".join(symbol for symbol in ActionStatus.__members__.values())
            logger.error(
                f"Invalid status value received: {status!r}. "
                f"Allowed values are: {allowed}"
            )
            raise ValueError(
                f"Invalid status value: {status!r}. "
                f"Must be one of: {allowed}"
            )

        # Assign the enum member (SQLAlchemy will store the canonical name)
        action.status = validated_status  # type: ignore

        # Set completed_at when status changes to COMPLETED (P1-9)
        if validated_status == ActionStatus.COMPLETED:
            action.completed_at = datetime.utcnow()

        await self.db.commit()

        # Invalidate dashboard cache for this client
        from app.services.report_service import ReportService
        report_service = ReportService(self.db)
        await report_service.invalidate_cache(action.client_id)

        # Reload action with fresh DB state and eager-loaded relationships
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Action)
            .options(selectinload(Action.assignments).selectinload(Assignment.user))
            .where(Action.id == action.id)
        )
        action = result.scalar_one()

        # TODO: n8n workflow for "action.status_updated" not yet created.
        # Previously fired to base N8N_WEBHOOK_URL (no path) → 404.
        # Re-enable when n8n/workflows/action-status-updated.json is deployed.
        # payload = {
        #     "event": "action.status_updated",
        #     "action_id": action.id,
        #     "status": status,
        #     "title": str(action.title),
        # }
        # try:
        #     async with httpx.AsyncClient() as client:
        #         await client.post(f"{settings.N8N_WEBHOOK_URL}/action-status-updated", json=payload, timeout=5.0)
        # except Exception as e:
        #     logger.error(f"Failed to trigger n8n status notification: {e}")

        return action

    async def _resolve_assignee_with_full_signals(
        self,
        client_id: str,
        meeting_id: str,
        suggestion_title: str,
        suggestion_description: Optional[str],
        suggested_assignee: Optional[str],
        participant_names: List[str],
        speaker_mappings: List[Dict[str, Any]],
        transcription: Optional[Transcription],
    ) -> Dict[str, Any]:
        """
        Full multi-signal assignee resolution mirroring _identify_speakers pipeline.

        Signals:
        1. ONNX audio embedding matching (cosine distance against enrolled profiles)
        2. Regex self-introduction detection (text context)
        3. Mistral fusion (LLM-based resolution with candidate validation)
        4. Transcript keyword overlap (existing text-based matching)

        Returns: {assignee_name, confidence, source, method}
        """
        from app.services.speaker_profile_service import SpeakerProfileService
        from app.services.speaker_name_detector import detect_self_introduction
        from app.services.mistral_fusion_service import mistral_fusion_service
        from app.services.speaker_embedding_service import speaker_embedding_service
        from app.services.audio_segment_service import audio_segment_service

        INVALID_ASSIGNEES = {"", "null", "n/a", "non défini", "none", "undefined", "tbd", "tba"}

        # Build candidate list: participants + enrolled ONNX profiles
        profile_service = SpeakerProfileService(self.db)
        enrolled_profiles = await profile_service.get_profiles(client_id)
        profile_names = [p.resolved_name or p.name for p in enrolled_profiles if p.resolved_name or p.name]
        candidates = list(set(participant_names + profile_names))
        logger.info(f"learn_from_feedback candidates: {candidates}")

        signals = []

        # SIGNAL 1: ONNX Audio Matching — extract embedding per speaker, match profiles
        await speaker_embedding_service.initialize()
        if speaker_embedding_service.is_available and transcription and transcription.segments:
            # Group segments by speaker
            speaker_groups: Dict[str, List[Dict]] = {}
            for seg in transcription.segments:
                spk = seg.get("speaker", "Speaker 0")
                if spk not in speaker_groups:
                    speaker_groups[spk] = []
                speaker_groups[spk].append(seg)

            # Download audio from S3
            audio_path = await self._download_recording_audio(meeting_id)
            if audio_path:
                for speaker_label, segs in speaker_groups.items():
                    try:
                        segments_for_service = [
                            {"speaker": "target", "start": s.get("start", 0), "end": s.get("end", 0)}
                            for s in segs
                        ]
                        speaker_files = await audio_segment_service.extract_speaker_segments(
                            audio_file_path=audio_path, segments=segments_for_service
                        )
                        target_audio = speaker_files.get("target")
                        if target_audio and os.path.exists(target_audio):
                            embedding = await speaker_embedding_service.extract_embedding(target_audio)
                            if embedding is not None:
                                name, distance, conf_level = await profile_service.match_speaker(
                                    client_id=client_id, embedding=embedding
                                )
                                if name:
                                    audio_score = {"high": 0.90, "medium": 0.60, "low": 0.30}.get(conf_level, 0.30)
                                    signals.append({"source": "audio", "name": name, "score": audio_score})
                                    logger.info(f"Audio signal for {speaker_label}: {name} (score={audio_score:.2f})")
                            try:
                                os.remove(target_audio)
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(f"Audio matching failed for {speaker_label}: {e}")
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        # SIGNAL 2: Regex Self-Introduction Detection
        if transcription and transcription.full_text:
            text_context = transcription.full_text[:5000]  # Limit for performance
            detected_name = detect_self_introduction(text_context, candidates)
            if detected_name:
                signals.append({"source": "text", "name": detected_name, "score": 0.85})
                logger.info(f"Text signal (self-intro): {detected_name} (score=0.85)")

        # SIGNAL 3: Mistral Fusion (if no high-confidence signal yet)
        if not signals or all(s["score"] < 0.70 for s in signals):
            # Build text context from transcription segments grouped by speaker
            text_by_speaker = {}
            if transcription and transcription.segments:
                for seg in transcription.segments:
                    spk = seg.get("speaker", "Speaker 0")
                    text_by_speaker[spk] = text_by_speaker.get(spk, "") + " " + seg.get("text", "")

            for speaker_label, text_context in text_by_speaker.items():
                if not text_context.strip():
                    continue
                mistral_name, mistral_score, _ = await mistral_fusion_service.fuse_speaker_mapping(
                    speaker_label=speaker_label,
                    text_context=text_context.strip(),
                    audio_matches=[],
                    client_id=client_id,
                    candidates=candidates,
                )
                if mistral_name:
                    signals.append({"source": "llm", "name": mistral_name, "score": mistral_score})
                    logger.info(f"LLM signal for {speaker_label}: {mistral_name} (score={mistral_score:.2f})")

        # SIGNAL 4: Transcript Keyword Overlap (existing logic)
        if transcription and transcription.segments and suggestion_title:
            task_keywords = set((suggestion_title or "").lower().split() + (suggestion_description or "").lower().split())
            task_keywords = {w for w in task_keywords if len(w) > 3}
            best_speaker = None
            best_score = 0
            for seg in transcription.segments:
                seg_text = seg.get("text", "").lower()
                seg_words = set(seg_text.split())
                overlap = len(task_keywords & seg_words)
                if overlap > best_score:
                    best_score = overlap
                    best_speaker = seg.get("speaker")
            if best_speaker and best_score >= 2:
                resolved = best_speaker
                if best_speaker.startswith("Speaker "):
                    for m in speaker_mappings:
                        if m["speaker_label"] == best_speaker and m.get("resolved_name"):
                            resolved = m["resolved_name"]
                            break
                if resolved and not resolved.startswith("Speaker "):
                    keyword_score = min(best_score / 10.0, 0.75)
                    signals.append({"source": "keyword", "name": resolved, "score": keyword_score})
                    logger.info(f"Keyword signal: {resolved} (score={keyword_score:.2f}, overlap={best_score})")

        # AGGREGATE: weighted consensus (same as _identify_speakers)
        resolved_name = None
        confidence = 0.0
        method = "no_match"

        if signals:
            name_scores = {}
            name_sources = {}
            total_signal_weight = sum(s["score"] for s in signals)

            for sig in signals:
                name = sig["name"]
                name_scores[name] = name_scores.get(name, 0) + sig["score"]
                name_sources[name] = name_sources.get(name, []) + [sig["source"]]

            resolved_name = max(name_scores, key=name_scores.get)
            raw_score = name_scores[resolved_name]
            num_sources = len(name_sources[resolved_name])

            confidence = raw_score / total_signal_weight if total_signal_weight > 0 else 0.0
            if num_sources > 1:
                confidence = min(confidence * (1.0 + 0.15 * (num_sources - 1)), 1.0)
            other_score = total_signal_weight - raw_score
            if other_score > 0:
                conflict_ratio = other_score / raw_score
                confidence *= max(1.0 - conflict_ratio * 0.5, 0.3)

            method = "+".join(sorted(set(name_sources[resolved_name])))
            logger.info(f"Consensus: {resolved_name} (confidence={confidence:.2f}, sources={method})")

        # VALIDATION: name MUST be in candidates
        if resolved_name and resolved_name not in candidates:
            logger.warning(f"'{resolved_name}' not in candidates. Rejecting.")
            resolved_name = None
            confidence = 0.0
            method = "no_match"

        # FALLBACK: use suggested_assignee if valid and no consensus found
        if not resolved_name and suggested_assignee and str(suggested_assignee).strip().lower() not in INVALID_ASSIGNEES:
            resolved_name = str(suggested_assignee).strip()
            confidence = 0.50
            method = "suggested_assignee"

        return {
            "assignee_name": resolved_name,
            "confidence": confidence,
            "source": method,
        }

    async def _download_recording_audio(self, meeting_id: str) -> Optional[str]:
        """Download recording audio from S3 for embedding extraction."""
        try:
            from app.core.config import settings as app_settings, get_bucket_name
            result = await self.db.execute(
                select(Recording).where(Recording.meeting_id == meeting_id).order_by(Recording.created_at.desc()).limit(1)
            )
            recording = result.scalar_one_or_none()
            if not recording or not recording.file_path:
                return None

            loop = asyncio.get_event_loop()
            s3_client = boto3.client(
                "s3",
                endpoint_url=app_settings.S3_ENDPOINT,
                aws_access_key_id=app_settings.S3_ACCESS_KEY,
                aws_secret_access_key=app_settings.S3_SECRET_KEY,
            )
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                await loop.run_in_executor(
                    None,
                    lambda: s3_client.download_fileobj(get_bucket_name(str(recording.client_id)), recording.file_path, tmp)
                )
                return tmp.name
        except Exception as e:
            logger.warning(f"Failed to download recording audio: {e}")
            return None

    async def learn_from_feedback(self, suggestion_id: str, client_id: str, action: str, user_id: Optional[str] = None) -> None:
        """Records feedback and creates a real Action if accepted."""
        from sqlalchemy.orm import selectinload
        from app.models.meeting import Meeting
        from app.tasks.transcription_tasks import _save_pv_and_actions
        from app.services.assignee_resolver import AssigneeResolver
        from app.services.audit_service import AuditService
        from app.models.transcription import Speaker, Transcription
        stmt = (
            select(ActionSuggestion)
            .options(selectinload(ActionSuggestion.meeting).selectinload(Meeting.participants))
            .where(ActionSuggestion.id == suggestion_id)
            .where(ActionSuggestion.client_id == client_id)
        )
        res = await self.db.execute(stmt)
        suggestion = res.scalar_one_or_none()

        if not suggestion:
            logger.warning(f"Suggestion {suggestion_id} not found for feedback.")
            return

        if action == "accept":
            suggestion.status = SuggestionStatus.ACCEPTED

            if not suggestion.meeting_id:
                logger.error(
                    f"Suggestion {suggestion_id} has NULL meeting_id. "
                    f"Cannot create Action. Committing status change only."
                )
                await self.db.commit()
                return

            new_action_id = str(uuid.uuid4())
            new_action = Action(
                id=new_action_id,
                client_id=client_id,
                meeting_id=str(suggestion.meeting_id),
                title=suggestion.title,
                description=suggestion.description,
                status=ActionStatus.PENDING,
                priority="medium"
            )
            self.db.add(new_action)
            
            # CRITICAL RULE: NULL/EMPTY ASSIGNEES ARE FORBIDDEN
            # Every action MUST have an assignee. Resolution is MANDATORY.
            INVALID_ASSIGNEES = {"", "null", "n/a", "non défini", "none", "undefined", "tbd", "tba"}
            
            # ALWAYS gather resolution data
            participant_names = [p.name for p in suggestion.meeting.participants if p.name] if suggestion.meeting.participants else []
            
            # Get speaker mappings with resolved_name (include global profiles with meeting_id=NULL for this client)
            speaker_stmt = select(Speaker).where(
                Speaker.client_id == client_id,
                or_(Speaker.meeting_id == suggestion.meeting_id, Speaker.meeting_id.is_(None))
            )
            speaker_result = await self.db.execute(speaker_stmt)
            speakers = speaker_result.scalars().all()
            speaker_mappings = [
                {
                    "speaker_label": s.name,
                    "resolved_name": s.resolved_name or s.name,
                    "confidence": s.mapping_confidence if s.mapping_confidence is not None else 0.5,
                    "method": s.mapping_method or "unknown",
                    "user_id": s.user_id,
                }
                for s in speakers
            ]
            
            # Get all client users for directory resolution
            all_users_stmt = select(User).where(User.client_id == client_id, User.deleted_at.is_(None))
            all_users_result = await self.db.execute(all_users_stmt)
            all_users = all_users_result.scalars().all()
            client_users = [
                {"id": str(u.id), "full_name": u.full_name, "email": u.email}
                for u in all_users if u.full_name or u.email
            ]
            
            # Use AssigneeResolver for professional resolution
            resolver = AssigneeResolver(
                speaker_mappings=speaker_mappings,
                participant_names=participant_names,
                client_users=client_users,
            )
            
            # Determine single speaker for fallback
            resolved_speakers = {m["resolved_name"]: m for m in speaker_mappings if m.get("resolved_name")}
            single_speaker = list(resolved_speakers.keys())[0] if len(resolved_speakers) == 1 else None
            
            # Load transcription for signal pipeline
            trans_stmt = select(Transcription).where(
                Transcription.meeting_id == suggestion.meeting_id,
                Transcription.client_id == client_id,
            )
            trans_result = await self.db.execute(trans_stmt)
            transcription = trans_result.scalar_one_or_none()

            # FULL SIGNAL PIPELINE: ONNX + Mistral + Gladia + DB participants + keyword
            try:
                resolution_result = await self._resolve_assignee_with_full_signals(
                    client_id=client_id,
                    meeting_id=str(suggestion.meeting_id),
                    suggestion_title=suggestion.title,
                    suggestion_description=suggestion.description,
                    suggested_assignee=suggestion.suggested_assignee,
                    participant_names=participant_names,
                    speaker_mappings=speaker_mappings,
                    transcription=transcription,
                )
            except Exception as e:
                logger.error(f"Signal resolution failed for suggestion {suggestion_id}: {e}")
                resolution_result = {
                    "assignee_name": suggestion.suggested_assignee,
                    "confidence": 0.50,
                    "source": "error_fallback",
                }

            assignee_name = resolution_result["assignee_name"]
            resolution_source = resolution_result["source"]
            resolution_confidence = resolution_result["confidence"]

            logger.info(
                f"learn_from_feedback signal resolution: '{assignee_name}' "
                f"(confidence={resolution_confidence:.2f}, source={resolution_source})"
            )

            # FALLBACKS if full signal pipeline didn't resolve
            if not assignee_name and single_speaker:
                assignee_name = single_speaker
                resolution_source = "single_speaker_fallback"

            if not assignee_name and participant_names:
                assignee_name = participant_names[0]
                resolution_source = "first_participant_fallback"
            
            # FINAL SAFETY: If still no assignee, log critical error but still create external assignment
            if not assignee_name:
                logger.critical(
                    f"[ASSIGNEE_CRITICAL] No assignee resolved for suggestion {suggestion_id} — "
                    f"this should NEVER happen. Creating unassigned action."
                )
                # Still commit the action without assignment — but this is a bug
                await self.db.commit()
                return
            
            resolution = resolver.resolve(assignee_name, single_speaker=single_speaker)
            
            if resolution.user_id:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=new_action_id,
                    user_id=resolution.user_id
                )
                logger.info(
                    f"learn_from_feedback: resolved '{assignee_name}' to user_id '{resolution.user_id}' via {resolution.matched_via} (source: {resolution_source})"
                )
                # Audit log (ISO 27001)
                await AuditService.log_action(
                    db=self.db,
                    client_id=client_id,
                    action="ACTION_ASSIGNED",
                    table_name="assignments",
                    record_id=assignment.id,
                    new_values={
                        "action_id": new_action_id,
                        "user_id": resolution.user_id,
                        "assignee_name": assignee_name,
                        "matched_via": resolution.matched_via,
                        "confidence": resolution.confidence,
                        "source": "learn_from_feedback",
                        "resolution_source": resolution_source,
                    },
                    ip_address="internal",
                    user_agent="frontend",
                )
            else:
                # External assignment
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=new_action_id,
                    external_name=resolution.external_name or assignee_name,
                    external_email=resolution.external_email,
                )
                logger.info(
                    f"learn_from_feedback: external assignment for '{assignee_name}' via {resolution.matched_via} (source: {resolution_source})"
                )
                # Audit log (ISO 27001)
                await AuditService.log_action(
                    db=self.db,
                    client_id=client_id,
                    action="ACTION_ASSIGNED_EXTERNAL",
                    table_name="assignments",
                    record_id=assignment.id,
                    new_values={
                        "action_id": new_action_id,
                        "external_name": resolution.external_name or assignee_name,
                        "external_email": resolution.external_email,
                        "matched_via": resolution.matched_via,
                        "confidence": resolution.confidence,
                        "is_ambiguous": resolution.is_ambiguous,
                        "source": "learn_from_feedback",
                        "resolution_source": resolution_source,
                    },
                    ip_address="internal",
                    user_agent="frontend",
                )
            self.db.add(assignment)
            
            logger.info(f"Suggestion {suggestion_id} accepted and converted to Action {new_action.id}")
        elif action == "reject":
            suggestion.status = SuggestionStatus.REJECTED
        
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
        base_lang = target_language.split('-')[0] if target_language else "fr"
        target_lang_name = lang_names.get(base_lang, "French")

        system_content = f"""You are a professional translator. Translate the 'title' and 'description' of the following action suggestions into {target_lang_name}. 
CRITICAL: Return ONLY a valid JSON object with a single key "suggestions" containing the array of translated objects.
Example format:
{{
  "suggestions": [
    {{ "id": "...", "title": "translated...", "description": "translated..." }}
  ]
}}"""
        
        payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": json.dumps(suggestions_data)}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=45.0)
                response.raise_for_status()
                result = response.json()
                content_str = result["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                
                # Robustly extract the array
                if "suggestions" in parsed and isinstance(parsed["suggestions"], list):
                    return parsed["suggestions"]
                elif isinstance(parsed, list):
                    return parsed
                else:
                    logger.error(f"Unexpected JSON structure from Mistral translation: {parsed}")
                    return suggestions_data
        except Exception as e:
            logger.error(f"Failed to translate suggestions: {e}")
            return suggestions_data

    async def get_due_actions(self, client_id: str) -> List[Action]:
        """Für tägliche Reminder (via Celery)"""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        result = await self.db.execute(
            select(Action).where(
                Action.due_date <= tomorrow, Action.status != "COMPLETED", Action.client_id == client_id
            )
        )
        return list(result.scalars().all())

    async def escalate_overdue(self, action_id: str) -> None:
        """Eskalation an Manager"""
        # TODO: n8n workflow for "action.escalate" not yet created.
        # Previously fired to base N8N_WEBHOOK_URL (no path) → 404.
        # Re-enable when n8n/workflows/action-escalate.json is deployed.
        # payload = {"event": "action.escalate", "action_id": action_id}
        # try:
        #     async with httpx.AsyncClient() as client:
        #         await client.post(f"{settings.N8N_WEBHOOK_URL}/action-escalate", json=payload, timeout=5.0)
        # except Exception as e:
        #     logger.error(f"Failed to trigger n8n escalate notification: {e}")
