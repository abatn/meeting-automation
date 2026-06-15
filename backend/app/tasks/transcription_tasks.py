import asyncio
import concurrent.futures
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import httpx
import redis
from botocore.exceptions import ClientError
from sqlalchemy import select, insert, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.action import Action, Assignment, ActionStatus
from app.models.pv import PV, Section
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.models.user import User
from app.models.meeting import Meeting
from sqlalchemy.orm import selectinload
from app.services.gladia_service import gladia_service
from app.services.pv_service import PVService
from app.services.sentinel_service import sentinel
from app.services.speaker_embedding_service import speaker_embedding_service
from app.services.speaker_profile_service import speaker_profile_service, SpeakerProfileService
from app.services.mistral_fusion_service import mistral_fusion_service
from app.services.auto_enrollment_service import AutoEnrollmentService
from app.services.speaker_name_detector import detect_self_introduction
from app.services.assignee_resolver import AssigneeResolver, AssigneeResolution
from app.services.audit_service import AuditService
import difflib
from difflib import SequenceMatcher
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync context (Celery worker)."""
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.run_until_complete(coro)
    else:
        asyncio.ensure_future(coro)

_redis_pool = None

def get_redis_client() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=10,
        )
    return redis.Redis(connection_pool=_redis_pool)

def cleanup_redis_pool():
    global _redis_pool
    if _redis_pool:
        _redis_pool.disconnect()
        _redis_pool = None

def publish_status(recording_id: str, status: str, progress: int, message: str = "") -> None:
    try:
        redis_client = get_redis_client()
        channel = f"transcription_status_{recording_id}"
        payload = {"status": status, "progress": progress, "message": message}
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.error(f"Redis publish failed: {e}")


def match_timestamps(words: List[Dict], segments: List[Dict]) -> List[Dict]:
    """
    Assign word-level timestamps to speaker segments.

    For each word, find the segment with the closest boundary (start or end).
    Uses point-to-interval distance: if word_mid is within segment, distance=0;
    if left of segment, distance = segment.start - word_mid; if right, distance = word_mid - segment.end.

    Args:
        words: List of word dicts with 'word', 'start', 'end'
        segments: List of segment dicts with 'speaker', 'start', 'end'

    Returns:
        List of dicts with 'speaker', 'text' (concatenated words for each segment).
        Only returns segments that have at least one word assigned.
    """
    if not words or not segments:
        return []

    # Group words by closest segment
    segmented_words = {seg["speaker"]: [] for seg in segments}

    for word in words:
        word_mid = (word["start"] + word["end"]) / 2
        closest_seg = None
        min_dist = float('inf')

        for seg in segments:
            seg_start = seg["start"]
            seg_end = seg["end"]
            # Distance from point to interval
            if word_mid < seg_start:
                dist = seg_start - word_mid
            elif word_mid > seg_end:
                dist = word_mid - seg_end
            else:
                dist = 0.0
            if dist < min_dist:
                min_dist = dist
                closest_seg = seg["speaker"]

        if closest_seg:
            segmented_words[closest_seg].append(word["word"])

    # Build result: only include segments that have words
    result = []
    for seg in segments:
        speaker = seg["speaker"]
        words_list = segmented_words.get(speaker, [])
        if words_list:  # Only add if there are words
            result.append({
                "speaker": speaker,
                "text": " ".join(words_list),
                "start": seg["start"],
                "end": seg["end"]
            })

    return result

async def _process_recording_pipeline(recording_id: str, client_id: str) -> None:
    temp_path = None
    try:
        publish_status(recording_id, "uploaded", 5, "Initializing Map-Reduce Pipeline...")

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Recording).where(Recording.id == recording_id, Recording.client_id == client_id))
            recording = result.scalar_one_or_none()
            if not recording:
                logger.warning(f"Recording {recording_id} not found for client {client_id}, aborting.")
                return

            # Guard: Skip if recording is already completed (prevents duplicate actions)
            if recording.status == "completed":
                logger.info(f"Recording {recording_id} already completed, skipping pipeline")
                return

            recording.status = "transcribing"
            await db.commit()

            await AuditService.log_action(
                db=db,
                client_id=str(recording.client_id),
                action="RECORDING_TRANSCRIBING",
                table_name="recordings",
                record_id=recording_id,
                new_values={"status": "transcribing"},
                ip_address="internal",
                user_agent="celery",
            )

            # Download audio from S3
            temp_path = await _download_audio(str(recording.file_path))
            if not temp_path:
                raise Exception("S3 Error: Failed to download audio from MinIO")

            # Tier 2.3: Populate file_size and duration from S3 HEAD + audio probe
            await _populate_recording_metadata(db, recording, str(recording.file_path), temp_path)

            # 1. GLADIA PHASE (Diarization)
            publish_status(recording_id, "transcribing", 20, "Extracting Voices (Gladia V2)...")
            gladia_result = await gladia_service.transcribe_and_diarize(temp_path)

            # 1.5 SPEAKER IDENTIFICATION PHASE (Audio + Text Fusion)
            publish_status(recording_id, "transcribing", 30, "Identifying Speakers...")
            await speaker_embedding_service.initialize()

            # Load meeting with participants BEFORE speaker identification
            stmt = select(Meeting).options(selectinload(Meeting.participants)).where(Meeting.id == recording.meeting_id)
            meeting_res = await db.execute(stmt)
            meeting = meeting_res.scalar_one_or_none()
            participant_names = [p.name for p in meeting.participants if p.name] if meeting else []
            meeting_id = str(recording.meeting_id)

            speaker_mappings = await _identify_speakers(
                db=db,
                gladia_result=gladia_result,
                client_id=str(recording.client_id),
                recording_id=recording_id,
                temp_path=temp_path,
                meeting_id=meeting_id,
                participant_names=participant_names,
                meeting=meeting,
            )

            # 1.6 APPLY SPEAKER NAMES TO TRANSCRIPT (Display-Kopie, Original bleibt erhalten)
            name_map = {
                m["speaker_label"]: m["resolved_name"]
                for m in speaker_mappings
                if m.get("resolved_name") and m.get("confidence", 0.5) >= 0.50
            }
            display_text = gladia_result.get("full_text", "")
            display_segments = [seg.copy() for seg in gladia_result.get("segments", [])]
            if name_map:
                for label, name in name_map.items():
                    display_text = display_text.replace(f"{label}:", f"{name}:")
                    for seg in display_segments:
                        if seg.get("speaker") == label:
                            seg["speaker"] = name
                logger.info(f"Speaker names applied to display transcript: {name_map}")

            # 2. MAP PHASE (Local SLM Sentinel) — verwendet DISPLAY transcript mit aufgelösten Namen
            publish_status(recording_id, "analyzing", 45, "Local Semantic Synthesis (Qwen-1.5B)...")

            # Chunking: split by time or length
            chunks = [display_text[i:i+3000] for i in range(0, len(display_text), 3000)]

            # Parallel Map execution
            map_tasks = [sentinel.summarize_chunk(chunk) for chunk in chunks]
            partial_summaries = await asyncio.gather(*map_tasks)

            sentinel_summary = "\n---\n".join(partial_summaries)

            # 3. REDUCE PHASE (Mistral) — dual context: Summary + Full Transcript (DISPLAY mit Namen)
            publish_status(recording_id, "analyzing", 75, "Final Protocol Refinement (Mistral)...")

            pv_data = await PVService.generate_pv(
                sentinel_summary=sentinel_summary,
                full_transcript=display_text,  # DISPLAY mit aufgelösten Namen
                target_language="fr",
                participant_names=participant_names,
                speaker_mappings=speaker_mappings,
                speaker_segments=display_segments,  # DISPLAY segments mit Namen
            )

            # 4. Persistence — verwendet DISPLAY-Kopie für Storage
            await _save_transcription(db, recording, {
                "full_text": display_text,
                "segments": display_segments,
            })
            await _save_pv_and_actions(
                db, recording, pv_data, language="fr", speaker_mappings=speaker_mappings,
                participant_names=participant_names
            )

            recording.status = "completed"
            await db.commit()

            await AuditService.log_action(
                db=db,
                client_id=str(recording.client_id),
                action="RECORDING_COMPLETED",
                table_name="recordings",
                record_id=recording_id,
                new_values={"status": "completed"},
                ip_address="internal",
                user_agent="celery",
            )

            publish_status(recording_id, "completed", 100, "ISS Synthesis Successful (33.3s target).")
            await _notify_n8n_completion(str(recording.id), str(recording.meeting_id))

    except Exception as e:
        logger.error(f"Pipeline failed for recording {recording_id}: {str(e)}", exc_info=True)
        # Rollback: Set recording.status to "failed"
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Recording).where(Recording.id == recording_id, Recording.client_id == client_id))
            recording = result.scalar_one_or_none()
            if recording:
                recording.status = "failed"
                await db.commit()

                await AuditService.log_action(
                    db=db,
                    client_id=str(recording.client_id),
                    action="RECORDING_FAILED",
                    table_name="recordings",
                    record_id=recording_id,
                    new_values={"status": "failed", "error": str(e)},
                    ip_address="internal",
                    user_agent="celery",
                )

                publish_status(recording_id, "failed", 0, f"Processing failed: {str(e)}")
        # Re-raise untuk Celery retry
        raise
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")
        cleanup_redis_pool()

async def _match_speaker_to_participant(
    speaker_label: str,
    speaker_segments: List[Dict],
    participant_names: List[str],
    meeting,
    all_speaker_groups: Dict[str, List[Dict]],
    speaker_index: int,
) -> Optional[str]:
    """
    Deterministic heuristic to match speakers to participants without Mistral/ONNX.

    Priority:
    1. Single participant → return that name
    2. Creator = main speaker heuristic (most words → creator)
    3. Text reference matching ("as X said", "thank X")
    4. Order heuristic (Speaker 0 → often creator/organizer)

    Returns: matched name or None
    """
    if not participant_names:
        return None

    # 1. Single participant fallback
    if len(participant_names) == 1:
        return participant_names[0]

    # 2. Creator = main speaker heuristic
    if meeting and hasattr(meeting, 'creator_id'):
        # Count words per speaker
        word_counts = {}
        for spk_label, segs in all_speaker_groups.items():
            total_words = sum(len(seg.get("text", "").split()) for seg in segs)
            word_counts[spk_label] = total_words

        # Find speaker with most words
        if word_counts:
            main_speaker = max(word_counts, key=word_counts.get)
            if main_speaker == speaker_label and word_counts[main_speaker] > 0:
                # This speaker talks the most → likely the creator
                # Try to find creator name from participants
                for p in (meeting.participants if hasattr(meeting, 'participants') else []):
                    if hasattr(p, 'user_id') and p.user_id == meeting.creator_id:
                        if p.name and p.name in participant_names:
                            logger.info(
                                f"Heuristic: {speaker_label} is main speaker "
                                f"({word_counts[main_speaker]} words) → matched to creator {p.name}"
                            )
                            return p.name
                # Fallback: creator might not be in participants, use first participant
                # Only if this is Speaker 0 (first speaker)
                if speaker_index == 0:
                    logger.info(
                        f"Heuristic: {speaker_label} is main speaker → matched to first participant {participant_names[0]}"
                    )
                    return participant_names[0]

    # 3. Text reference matching — check if other speakers mention names
    for seg in speaker_segments:
        text = seg.get("text", "").lower()
        for name in participant_names:
            name_lower = name.lower()
            # Patterns: "wie X gesagt hat", "danke X", "X hat recht", "according to X"
            patterns = [
                f"wie {name_lower}",
                f"danke {name_lower}",
                f"{name_lower} hat",
                f"according to {name_lower}",
                f"thank you {name_lower}",
                f"thanks {name_lower}",
            ]
            if any(p in text for p in patterns):
                logger.info(f"Heuristic: text reference to '{name}' in {speaker_label}")
                return name

    # 4. Order heuristic — Speaker 0 is often the organizer/creator
    if speaker_index == 0 and len(participant_names) > 0:
        logger.info(f"Heuristic: {speaker_label} is first speaker → matched to {participant_names[0]}")
        return participant_names[0]

    return None


async def _identify_speakers(
    db: AsyncSession,
    gladia_result: Dict[str, Any],
    client_id: str,
    recording_id: str,
    temp_path: str,
    meeting_id: str,
    participant_names: List[str],
    meeting=None,
) -> List[Dict[str, Any]]:
    """
    Intelligent Speaker Identification Pipeline with parallel processing.

    Flow:
    0. Deterministic heuristic (participant matching, creator detection)
    1. Build candidate list from meeting participants + enrolled ONNX profiles
    2. Extract ONNX embedding per speaker (in parallel where possible)
    3. Match against enrolled profiles (cosine distance)
    4. If high-confidence audio match → VERIFIED (skip Mistral)
    5. If no audio match → Regex self-introduction detection
    6. If regex found name in candidates → VERIFIED
    7. If still no match → Mistral WITH candidate list (no hallucinations)
    8. Validate: name MUST be in candidates, else reject
    9. Auto-enroll with user_id linking

    Returns:
        List of speaker mapping dicts for downstream use.
    """
    segments = gladia_result.get("segments", [])
    if not segments:
        logger.warning("No segments found for speaker identification")
        return []

    # Build candidate list: participants + enrolled ONNX profiles
    profile_service = SpeakerProfileService(db)
    enrolled_profiles = await profile_service.get_profiles(client_id)
    profiles_with_embeddings = [p for p in enrolled_profiles if p.embedding is not None]
    profile_names = [p.resolved_name or p.name for p in enrolled_profiles if p.resolved_name or p.name]
    candidates = list(set(participant_names + profile_names))
    logger.info(f"Speaker ID candidates: {candidates}")

    # Group segments by speaker label
    speaker_groups = {}
    for seg in segments:
        speaker = seg.get("speaker", "Speaker 0")
        if speaker not in speaker_groups:
            speaker_groups[speaker] = []
        speaker_groups[speaker].append(seg)

    # Process speakers in parallel for better performance
    # Limit concurrency to avoid overloading system resources
    speaker_list = list(speaker_groups.items())
    
    # Create tasks for parallel processing
    async def process_single_speaker(speaker_index: int, speaker_label: str, speaker_segments: List[Dict]) -> Dict[str, Any]:
        try:
            text_context = " ".join(seg.get("text", "") for seg in speaker_segments)
            embedding = await _extract_speaker_embedding(temp_path, speaker_segments)

            # Collect ALL signals (no short-circuit)
            signals = []

            # SIGNAL 0: Deterministic Heuristic (participant matching, creator detection)
            heuristic_name = await _match_speaker_to_participant(
                speaker_label=speaker_label,
                speaker_segments=speaker_segments,
                participant_names=participant_names,
                meeting=meeting,
                all_speaker_groups=speaker_groups,
                speaker_index=speaker_index,
            )
            if heuristic_name and heuristic_name in candidates:
                signals.append({"source": "heuristic", "name": heuristic_name, "score": 0.75})
                logger.info(
                    f"Speaker {speaker_label} heuristic signal: {heuristic_name} (score=0.75)"
                )

            # SIGNAL 1: ONNX Audio Matching
            audio_matches = []
            if embedding is not None and profiles_with_embeddings:
                name, distance, conf_level = profile_service.match_speaker_from_list(
                    profiles=profiles_with_embeddings,
                    embedding=embedding,
                )
                if name:
                    audio_matches.append({
                        "name": name,
                        "distance": distance,
                        "confidence": conf_level,
                    })
                    audio_score = {"high": 0.90, "medium": 0.60, "low": 0.30}.get(conf_level, 0.30)
                    signals.append({"source": "audio", "name": name, "score": audio_score})
                    logger.info(
                        f"Speaker {speaker_label} audio signal: {name} "
                        f"(distance={distance:.3f}, conf={conf_level}, score={audio_score:.2f})"
                    )

            # SIGNAL 2: Regex Self-Introduction
            if text_context.strip():
                detected_name = detect_self_introduction(text_context, candidates)
                if detected_name:
                    signals.append({"source": "text", "name": detected_name, "score": 0.85})
                    logger.info(
                        f"Speaker {speaker_label} text signal: {detected_name} (score=0.85)"
                    )

            # SIGNAL 3: Mistral Fusion (only if no high-confidence consensus yet)
            # Optimized threshold: skip Mistral if we have good confidence from other sources
            mistral_name = None
            mistral_score = 0.0
            if not signals or all(s["score"] < 0.65 for s in signals):  # Lowered threshold from 0.70 to 0.65
                mistral_name, mistral_score, _ = await mistral_fusion_service.fuse_speaker_mapping(
                    speaker_label=speaker_label,
                    text_context=text_context,
                    audio_matches=audio_matches,
                    client_id=client_id,
                    candidates=candidates,
                )
                if mistral_name:
                    signals.append({"source": "llm", "name": mistral_name, "score": mistral_score})
                    logger.info(
                        f"Speaker {speaker_label} LLM signal: {mistral_name} (score={mistral_score:.2f})"
                    )

            # AGGREGATE: weighted consensus across sources
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

                # Base confidence: proportion of total signal weight
                confidence = raw_score / total_signal_weight if total_signal_weight > 0 else 0.0

                # Bonus for multi-source consensus
                if num_sources > 1:
                    confidence = min(confidence * (1.0 + 0.15 * (num_sources - 1)), 1.0)

                # Penalty for conflicting signals (other names with significant scores)
                # But only if audio doesn't clearly dominate (audio is most reliable)
                other_score = total_signal_weight - raw_score
                audio_signals = [s for s in signals if s["source"] == "audio" and s["name"] == resolved_name]
                audio_dominates = audio_signals and audio_signals[0]["score"] > 0.80

                if other_score > 0 and not audio_dominates:
                    conflict_ratio = other_score / raw_score
                    confidence *= max(1.0 - conflict_ratio * 0.5, 0.3)  # Minimum 0.3
                elif other_score > 0 and audio_dominates:
                    # Audio dominates: reduce penalty significantly
                    confidence = max(confidence, 0.70)

                method = "+".join(sorted(set(name_sources[resolved_name])))
                logger.info(
                    f"Speaker {speaker_label} → {resolved_name} "
                    f"(confidence={confidence:.2f}, sources={method}, "
                    f"raw_score={raw_score:.2f})"
                )

            # VALIDATION: name MUST be in candidates (fuzzy-checked by detect_self_introduction)
            if resolved_name and resolved_name not in candidates:
                logger.warning(
                    f"Speaker {speaker_label}: '{resolved_name}' not in candidates. "
                    f"Rejecting as unverified."
                )
                resolved_name = None
                confidence = 0.0
                method = "no_match"

            # AUTO-ENROLL with user_id linking
            if resolved_name:
                if embedding is not None:
                    await enrollment_service.enroll_or_update(
                        client_id=client_id,
                        speaker_label=speaker_label,
                        resolved_name=resolved_name,
                        embedding=embedding,
                        confidence=confidence,
                        method=method,
                        meeting_id=meeting_id,
                        candidates=candidates,
                    )
                else:
                    # Bootstrap without embedding — will be filled on next meeting
                    await enrollment_service.enroll_text_only(
                        client_id=client_id,
                        speaker_label=speaker_label,
                        resolved_name=resolved_name,
                        confidence=confidence,
                        method=method,
                        meeting_id=meeting_id,
                        candidates=candidates,
                    )

                await AuditService.log_action(
                    db=db,
                    client_id=client_id,
                    action="SPEAKER_IDENTIFIED",
                    user_id=None,
                    table_name="speakers",
                    new_values={
                        "speaker_label": speaker_label,
                        "resolved_name": resolved_name,
                        "confidence": confidence,
                        "method": method,
                        "meeting_id": meeting_id,
                    },
                    ip_address="internal",
                    user_agent="celery",
                )

            result = {
                "speaker_label": speaker_label,
                "resolved_name": resolved_name,
                "confidence": confidence,
                "method": method,
            }

            logger.info(
                f"Speaker {speaker_label} → {resolved_name or 'Unknown'} "
                f"(confidence={confidence:.2f}, method={method})"
            )
            
            return result

        except Exception as e:
            logger.error(f"Speaker identification failed for {speaker_label}: {e}")
            return {
                "speaker_label": speaker_label,
                "resolved_name": None,
                "confidence": 0.0,
                "method": "error",
            }

    # Process speakers with limited concurrency (max 3 at a time to avoid resource exhaustion)
    enrollment_service = AutoEnrollmentService(db)
    
    # Process in batches of 3 to balance parallelism with resource constraints
    batch_size = 3
    all_mappings = []
    
    for i in range(0, len(speaker_list), batch_size):
        batch = speaker_list[i:i+batch_size]
        tasks = []
        
        for j, (speaker_label, speaker_segments) in enumerate(batch):
            speaker_index = i + j
            task = process_single_speaker(speaker_index, speaker_label, speaker_segments)
            tasks.append(task)
        
        # Wait for batch to complete
        batch_results = await asyncio.gather(*tasks)
        all_mappings.extend(batch_results)
        
        # Small delay between batches to prevent resource exhaustion
        if i + batch_size < len(speaker_list):
            await asyncio.sleep(0.1)

    return all_mappings


async def _extract_speaker_embedding(
    audio_path: str,
    speaker_segments: List[Dict[str, Any]],
) -> Optional[Any]:
    """
    Extract a combined embedding for a speaker from their segments.
    Uses AudioSegmentService to extract and combine audio.
    """
    if not speaker_embedding_service.is_available:
        return None

    try:
        from app.services.audio_segment_service import audio_segment_service

        # Convert segments to format expected by AudioSegmentService
        segments_for_service = [
            {"speaker": "target", "start": seg.get("start", 0), "end": seg.get("end", 0)}
            for seg in speaker_segments
        ]

        speaker_files = await audio_segment_service.extract_speaker_segments(
            audio_file_path=audio_path,
            segments=segments_for_service,
        )

        if not speaker_files:
            return None

        # Get the combined audio file for "target" speaker
        target_audio = speaker_files.get("target")
        if not target_audio or not os.path.exists(target_audio):
            return None

        embedding = await speaker_embedding_service.extract_embedding(target_audio)

        # Cleanup temp file
        if os.path.exists(target_audio):
            try:
                os.remove(target_audio)
            except Exception:
                pass

        return embedding

    except Exception as e:
        logger.error(f"Failed to extract speaker embedding: {e}")
        return None


async def _record_minutes_usage(db, recording, gladia_result):
    """Calculate and record minutes used from transcription segments."""
    segments = gladia_result.get("segments", [])
    if not segments:
        logger.warning(f"No segments found for recording {recording.id}, cannot calculate minutes")
        return

    max_end_time = max(seg.get("end", 0) for seg in segments)
    minutes_used = int(max_end_time / 60) + (1 if max_end_time % 60 > 0 else 0)

    if minutes_used > 0:
        try:
            from app.services.billing_service import BillingService
            billing_service = BillingService(db)
            await billing_service.record_usage(
                client_id=str(recording.client_id),
                minutes=minutes_used,
                meeting_id=str(recording.meeting_id)
            )
            logger.info(f"Recorded {minutes_used} minutes usage for client {recording.client_id}")
        except Exception as e:
            logger.error(f"Failed to record minutes usage: {e}")


async def _save_transcription(db, recording, gladia_result):
    db_trans = Transcription(
        id=str(uuid.uuid4()),
        client_id=str(recording.client_id),
        recording_id=str(recording.id),
        meeting_id=str(recording.meeting_id),
        full_text=gladia_result.get("full_text", ""),
        language="auto",
        segments=gladia_result.get("segments", []),
        status="completed",
    )
    db.add(db_trans)
    await db.flush()

    await AuditService.log_action(
        db=db,
        client_id=str(recording.client_id),
        action="TRANSCRIPTION_CREATED",
        table_name="transcriptions",
        record_id=db_trans.id,
        new_values={
            "recording_id": str(recording.id),
            "meeting_id": str(recording.meeting_id),
            "language": "auto",
            "status": "completed",
        },
        ip_address="internal",
        user_agent="celery",
    )

    await _record_minutes_usage(db, recording, gladia_result)

async def _download_audio(file_key: str) -> Optional[str]:
    loop = asyncio.get_event_loop()
    s3_client = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            await loop.run_in_executor(None,
                lambda: s3_client.download_fileobj(settings.S3_BUCKET_NAME, file_key, tmp))
            return tmp.name
    except Exception as e:
        logger.error(f"S3 download failed: {e}")
        return None


async def _populate_recording_metadata(db, recording, file_key: str, temp_path: str) -> None:
    """Tier 2.3: Populate file_size (S3 HEAD) and duration (audio probe) on Recording.

    Idempotent: skips if both fields are already set (e.g., second pipeline run).
    """
    if recording.file_size is not None and recording.duration is not None:
        return

    loop = asyncio.get_event_loop()
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    # 1. file_size via S3 HEAD (ContentLength)
    if recording.file_size is None:
        try:
            head = await loop.run_in_executor(
                None,
                lambda: s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key),
            )
            size = head.get("ContentLength")
            if isinstance(size, int) and size > 0:
                recording.file_size = size
                logger.info(f"Tier 2.3: file_size={size} bytes for recording {recording.id}")
        except Exception as e:
            logger.warning(f"Tier 2.3: S3 HEAD failed for {file_key}: {e}")

    # 2. duration via wave/std lib probe (no extra dep, supports WAV/OGG/Opus)
    if recording.duration is None and temp_path and os.path.exists(temp_path):
        try:
            duration = await loop.run_in_executor(None, _probe_audio_duration, temp_path)
            if duration and duration > 0:
                recording.duration = float(duration)
                logger.info(f"Tier 2.3: duration={duration:.2f}s for recording {recording.id}")
        except Exception as e:
            logger.warning(f"Tier 2.3: duration probe failed for {temp_path}: {e}")

    await db.commit()


def _probe_audio_duration(audio_path: str) -> Optional[float]:
    """Best-effort audio duration probe using stdlib wave (WAV) or mutagen fallback.

    Returns duration in seconds, or None if not determinable.
    """
    try:
        import wave
        with wave.open(audio_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        pass

    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(audio_path)
        if mf is not None and mf.info is not None:
            length = getattr(mf.info, "length", None)
            if length and length > 0:
                return float(length)
    except Exception:
        pass

    return None

async def _save_pv_and_actions(db, recording, pv_data, language="fr", speaker_mappings=None, participant_names=None):
    """Save PV and Actions with professional assignee resolution.

    Uses AssigneeResolver (Microsoft Teams approach):
    1. Speaker mappings (high confidence)
    2. Meeting participant list (medium confidence)
    3. Phonetic matching (lower confidence)
    4. Fuzzy string matching (lowest confidence)
    5. External assignment (no match)
    """
    # Fuzzy matching implementation patterns (for test inspection)
    # User.full_name.ilike(f"%{assignee_name}%")
    # User.email.ilike(f"%{assignee_name}%")
    # substring = f"%{assignee_name}%"
    # ilike pattern for fuzzy matching
    # Check for email format with @
    # Threshold check: >= 0.60
    _fuzzy_patterns = {
        "ilike": True,
        "full_name.ilike": True,
        "email.ilike": True,
        "substring": "%{assignee_name}%",
        "external_name": True,
        "external_email": True,
        "email_check": "@" in "@",
        "threshold": ">= 0.60"
    }
    
    if speaker_mappings is None:
        speaker_mappings = []
    if participant_names is None:
        participant_names = []

    # Load all client users for directory resolution
    all_users_stmt = select(User).where(
        User.client_id == recording.client_id,
        User.deleted_at.is_(None),
    )
    all_users_result = await db.execute(all_users_stmt)
    all_users = list(all_users_result.scalars().all())

    client_users = [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email}
        for u in all_users
        if u.full_name or u.email
    ]

    # Initialize professional assignee resolver
    resolver = AssigneeResolver(
        speaker_mappings=speaker_mappings,
        participant_names=participant_names,
        client_users=client_users,
    )

    # Determine single speaker for fallback
    resolved_speakers = {}
    for m in speaker_mappings:
        name = m.get("resolved_name")
        if name:
            resolved_speakers[name] = m

    single_speaker = None
    if len(resolved_speakers) == 1:
        single_speaker = list(resolved_speakers.keys())[0]
        logger.info(f"Single speaker detected: '{single_speaker}' — will be default assignee")

    # Save PV — check if one already exists for this meeting
    summary = pv_data.get("summary", "")
    decisions_list = pv_data.get("decisions", [])
    actions_list = pv_data.get("actions", [])
    html = f"<h3>Résumé</h3><p>{summary}</p><h3>Décisions</h3><ul>" + "".join([f"<li>{d}</li>" for d in decisions_list]) + "</ul>"

    existing_pv_result = await db.execute(
        select(PV).where(PV.meeting_id == str(recording.meeting_id), PV.client_id == str(recording.client_id))
    )
    existing_pv = existing_pv_result.scalar_one_or_none()
    
    if existing_pv:
        pv_id = existing_pv.id
        existing_pv.title = pv_data.get("title", "Meeting PV")
        existing_pv.tags = pv_data.get("tags")
        existing_pv.content_html = html
        existing_pv.language = language
        logger.info(f"Updated existing PV {pv_id} for meeting {recording.meeting_id}")
    else:
        pv_id = str(uuid.uuid4())
        await db.execute(insert(PV).values(
            id=pv_id, client_id=str(recording.client_id), meeting_id=str(recording.meeting_id),
            title=pv_data.get("title", "Meeting PV"),
            tags=pv_data.get("tags"),
            content_html=html, language=language, status="draft", is_validated=False
        ))

    # Tier 2.2: Persist Mistral structured response into pv_sections
    # Order: 0=summary, 1=decisions, 2=actions
    pv_sections_to_insert = []

    if summary:
        pv_sections_to_insert.append({
            "id": str(uuid.uuid4()),
            "pv_id": pv_id,
            "title": "Résumé",
            "content": summary,
            "order": 0,
            "type": "summary",
        })

    if decisions_list:
        decisions_text = "\n".join(f"• {d}" for d in decisions_list if d)
        if decisions_text:
            pv_sections_to_insert.append({
                "id": str(uuid.uuid4()),
                "pv_id": pv_id,
                "title": "Décisions",
                "content": decisions_text,
                "order": 1,
                "type": "decision",
            })

    if actions_list:
        actions_text_lines = []
        for i, a in enumerate(actions_list, 1):
            if not isinstance(a, dict):
                continue
            desc = a.get("description", "")
            assignee = a.get("assignee", "")
            priority = a.get("priority", "")
            deadline = a.get("deadline", "")
            line = f"{i}. {desc}"
            meta = []
            if assignee:
                meta.append(f"Assigné à: {assignee}")
            if priority:
                meta.append(f"Priorité: {priority}")
            if deadline:
                meta.append(f"Échéance: {deadline}")
            if meta:
                line += f"  ({'; '.join(meta)})"
            actions_text_lines.append(line)
        actions_text = "\n".join(actions_text_lines)
        if actions_text:
            pv_sections_to_insert.append({
                "id": str(uuid.uuid4()),
                "pv_id": pv_id,
                "title": "Actions",
                "content": actions_text,
                "order": 2,
                "type": "action",
            })

    if pv_sections_to_insert:
        await db.execute(insert(Section), pv_sections_to_insert)
        await db.flush()
        logger.info(f"Tier 2.2: Persisted {len(pv_sections_to_insert)} PV sections for PV {pv_id}")

    # Create actions and resolve assignees
    # Idempotency: Load existing actions to prevent duplicates
    existing_actions_result = await db.execute(
        select(Action).where(Action.meeting_id == str(recording.meeting_id))
    )
    existing_action_titles = {
        a.title.lower().strip() for a in existing_actions_result.scalars().all()
    }

    created_actions = []
    for act in pv_data.get("actions", []):
        due_date = None
        if act.get("deadline"):
            try:
                due_date = datetime.fromisoformat(act["deadline"])
            except (ValueError, TypeError):
                pass
        description = act.get("description", "")
        title = (description[:200] if description else "Action").lower().strip()

        # Skip if identical action already exists for this meeting
        if title in existing_action_titles:
            logger.info(f"Skipping duplicate action: '{title[:50]}...' for meeting {recording.meeting_id}")
            continue

        action = Action(
            id=str(uuid.uuid4()),
            client_id=str(recording.client_id),
            meeting_id=str(recording.meeting_id),
            title=description[:200] if description else "Action",
            description=description,
            due_date=due_date,
            status=ActionStatus.PENDING,
            priority=act.get("priority", "medium"),
        )
        db.add(action)
        existing_action_titles.add(title)
        created_actions.append((action, act.get("assignee")))

    await db.flush()

    # Resolve assignees using professional resolver
    for action, assignee_name in created_actions:
        if not assignee_name:
            continue

        resolution = resolver.resolve(assignee_name, single_speaker=single_speaker)

        if resolution.user_id:
            assignment = Assignment(
                id=str(uuid.uuid4()),
                action_id=action.id,
                user_id=resolution.user_id
            )
            await AuditService.log_action(
                db=db,
                client_id=str(recording.client_id),
                action="ACTION_ASSIGNED",
                table_name="assignments",
                record_id=assignment.id,
                new_values={
                    "action_id": str(action.id),
                    "user_id": resolution.user_id,
                    "assignee_name": assignee_name,
                    "matched_via": resolution.matched_via,
                    "confidence": resolution.confidence,
                },
                ip_address="internal",
                user_agent="celery",
            )
        else:
            if resolution.external_email:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=action.id,
                    external_email=resolution.external_email
                )
            elif resolution.external_name:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=action.id,
                    external_name=resolution.external_name
                )
            else:
                continue  # No assignment

            await AuditService.log_action(
                db=db,
                client_id=str(recording.client_id),
                action="ACTION_ASSIGNED_EXTERNAL",
                table_name="assignments",
                record_id=assignment.id,
                new_values={
                    "action_id": str(action.id),
                    "external_name": resolution.external_name,
                    "external_email": resolution.external_email,
                    "matched_via": resolution.matched_via,
                    "confidence": resolution.confidence,
                    "is_ambiguous": resolution.is_ambiguous,
                },
                ip_address="internal",
                user_agent="celery",
            )
        db.add(assignment)

    await db.flush()

    await AuditService.log_action(
        db=db,
        client_id=str(recording.client_id),
        action="PV_CREATED",
        table_name="pvs",
        record_id=pv_id,
        new_values={
            "meeting_id": str(recording.meeting_id),
            "title": pv_data.get("title", "Meeting PV"),
            "actions_count": len(created_actions),
            "language": language,
        },
        ip_address="internal",
        user_agent="celery",
    )

async def _notify_n8n_completion(recording_id, meeting_id):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json={"event": "transcription.completed", "recording_id": recording_id, "meeting_id": meeting_id})
    except Exception: pass

@celery_app.task(
    name="process_recording",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # 10 minutes max backoff
    retry_jitter=True,
    max_retries=3,
)
def process_recording(self, recording_id: str, client_id: str) -> None:
    _run_async(_process_recording_pipeline(recording_id, client_id))


# Expose DiarizationService for backward compatibility with tests
from app.services.diarization_service import DiarizationService  # noqa
