#!/usr/bin/env python3
"""
Pipeline Benchmark Test — Offizielle Pipeline mit echten Services.

Erfordert:
    export SENTINEL_MODEL_PATH=/home/opc/meeting-automation/qwen2.5-1.5b-instruct-q4_k_m.gguf
    export E2E_TEST=true
    PATH="$HOME/bin:$PATH"  # ffmpeg
    pytest tests/performance/test_pipeline_benchmark.py -v -s

Verwendet: _process_recording_pipeline() wie die offizielle Pipeline.
Thresholds: Lokale Messungen, ARM64, 3 enrollte Profiles, 9-Min Audio.
"""
import io
import json
import os
import struct
import time
import uuid
import wave
from datetime import datetime, timezone

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.recording import Recording

# ---------------------------------------------------------------------------
# Thresholds — echte Messungen lokal (ARM64, 3 Profiles, 9-Min Audio)
# Messung: 2026-09-19
# ---------------------------------------------------------------------------
RATE_GLADIA_S = 17.80
RATE_GLADIA_RANGE = (10.0, 25.0)

RATE_SPEAKERID_S_PER_SEG = 0.476
RATE_SPEAKERID_RANGE = (0.2, 1.0)

RATE_ONNX_S_PER_SEG = 0.951
RATE_ONNX_RANGE = (0.5, 2.0)

RATE_SENTINEL_S_PER_CHUNK = 63.2
RATE_SENTINEL_RANGE = (30.0, 120.0)

# Pipeline total: 158s ohne Sentinel LLM, ~348s mit Sentinel LLM (63.2×3 chunks)
PIPELINE_TOTAL_WITHOUT_SENTINEL = (120, 250)
PIPELINE_TOTAL_WITH_SENTINEL = (250, 500)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REAL_AUDIO_PATH = os.environ.get(
    "BENCHMARK_AUDIO_PATH",
    "/home/opc/meeting_benchmark.wav",
)


def _extract_msg(line: str) -> str:
    """Extract message from JSON log line or return raw line."""
    try:
        obj = json.loads(line.strip())
        return obj.get("message", "")
    except (json.JSONDecodeError, ValueError):
        return line


def _slice_wav(path: str, max_seconds: int) -> bytes:
    """Lese WAV-Datei und schneide auf max_seconds."""
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        total_frames = wf.getnframes()
        frames_to_read = min(sr * max_seconds, total_frames)
        raw = wf.readframes(frames_to_read)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(sr)
        out.writeframes(raw)
    return buf.getvalue()


def _parse_timing(logs: str) -> dict:
    """Extrahiere TIMING-Werte aus captured logs (JSON oder plain text)."""
    timings = {}
    for line in logs.split("\n"):
        if "TIMING:" not in line:
            continue
        msg = _extract_msg(line)
        if "TIMING:" not in msg:
            continue
        try:
            payload = msg.split("TIMING:")[1].strip()
            key = payload.split()[0]
            for part in payload.split():
                if part.startswith("duration="):
                    val = float(part.split("=")[1].rstrip("s"))
                    timings[key] = val
                    break
        except (IndexError, ValueError):
            continue
    return timings


def _parse_segments(logs: str) -> int:
    """Extrahiere Segment-Anzahl aus ONNX-TIMING-Log."""
    for line in logs.split("\n"):
        if "segments=" not in line:
            continue
        msg = _extract_msg(line)
        for part in msg.split():
            if part.startswith("segments="):
                try:
                    return int(part.split("=")[1])
                except ValueError:
                    pass
    return 0


def _parse_chunks(logs: str) -> int:
    """Extrahiere Chunk-Anzahl aus Sentinel-Log."""
    for line in logs.split("\n"):
        if "sentinel_chunks" not in line or "count=" not in line:
            continue
        msg = _extract_msg(line)
        for part in msg.split():
            if part.startswith("count="):
                try:
                    return int(part.split("=")[1])
                except ValueError:
                    pass
    return 0


def _parse_speakers(logs: str) -> int:
    """Extrahiere Speaker-Anzahl aus SpeakerID-Log."""
    for line in logs.split("\n"):
        if "speaker_identification" not in line or "speakers=" not in line:
            continue
        msg = _extract_msg(line)
        for part in msg.split():
            if part.startswith("speakers="):
                try:
                    return int(part.split("=")[1])
                except ValueError:
                    pass
    return 0


def _sentinel_is_fallback(logs: str) -> bool:
    """Prüfe ob Sentinel im Fallback-Modus läuft."""
    for line in logs.split("\n"):
        if "llama-cpp-python not installed" in line:
            return True
    return False


async def _create_recording(
    db: AsyncSession,
    client_id: str,
    meeting_id: str,
    file_key: str,
) -> str:
    """Erstelle Recording-Objekt in DB."""
    recording_id = str(uuid.uuid4())
    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path=file_key,
        status="uploaded",
        format="audio/wav",
    )
    db.add(recording)
    await db.commit()
    return recording_id


async def _upload_to_s3(audio_bytes: bytes, file_key: str) -> None:
    """Lade Audio zu MinIO/S3 hoch."""
    import boto3
    from app.core.config import settings

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    bucket = settings.S3_BUCKET_NAME
    try:
        s3.create_bucket(Bucket=bucket)
    except Exception:
        pass
    s3.put_object(Bucket=bucket, Key=file_key, Body=audio_bytes, ContentType="audio/wav")


async def _create_enrolled_profiles(
    db: AsyncSession,
    client_id: str,
) -> list:
    """
    Erstelle 3 Speaker-Profiles mit echten ONNX-Embeddings.
    Verwendet 3s-Segmente aus dem Benchmark-Audio für Enrollment.
    """
    from app.services.speaker_embedding_service import speaker_embedding_service
    from app.services.speaker_profile_service import SpeakerProfileService

    await speaker_embedding_service.initialize()
    if not speaker_embedding_service.is_available:
        pytest.skip("ONNX model not available — cannot create real profiles")

    # Cleanup alte Benchmark-Profile
    await db.execute(
        text("DELETE FROM speakers WHERE client_id = :cid AND source = 'benchmark'"),
        {"cid": client_id},
    )
    await db.commit()

    profile_service = SpeakerProfileService(db)

    # Lade Benchmark-Audio
    import librosa
    audio_data, _ = librosa.load(REAL_AUDIO_PATH, sr=16000, mono=True)

    profiles = []
    for i, name in enumerate(["Ahmed", "Fatima", "Karim"]):
        # 3s Chunk an verschiedenen Stellen des Audio
        start_sample = i * 16000 * 30
        end_sample = min(start_sample + 16000 * 3, len(audio_data))
        chunk = audio_data[start_sample:end_sample]

        # WAV-Bytes erzeugen
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes((chunk * 32767).astype(np.int16).tobytes())

        embedding = await speaker_embedding_service.extract_embedding_from_bytes(wav_buf.getvalue())
        if embedding is not None:
            await profile_service.create_profile(
                client_id=client_id,
                name=name,
                embedding=embedding,
                source="benchmark",
            )
            profiles.append(name)
            print(f"  enrolled: {name} (embedding shape={embedding.shape})")
        else:
            print(f"  WARNUNG: {name} embedding=None")

    await db.commit()
    return profiles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wav_short() -> bytes:
    """2 Minuten Audio."""
    return _slice_wav(REAL_AUDIO_PATH, max_seconds=120)


@pytest.fixture
def wav_medium() -> bytes:
    """9 Minuten Audio (~132 Segmente bei Gladia)."""
    return _slice_wav(REAL_AUDIO_PATH, max_seconds=540)


@pytest.fixture
def wav_long() -> bytes:
    """14 Minuten Audio (komplett)."""
    with open(REAL_AUDIO_PATH, "rb") as f:
        return f.read()


@pytest_asyncio.fixture
async def benchmark_client_id(db_session: AsyncSession) -> str:
    return "test-client-id"


@pytest_asyncio.fixture
async def benchmark_meeting_id(db_session: AsyncSession, benchmark_client_id: str) -> str:
    from app.models.meeting import Meeting
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        client_id=benchmark_client_id,
        creator_id="test-user-id",
        title="Benchmark Test Meeting",
        description="Pipeline Benchmark",
        start_time=datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 9, 19, 11, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(meeting)
    await db_session.commit()
    return meeting_id


@pytest_asyncio.fixture
async def enrolled_profiles(
    db_session: AsyncSession,
    benchmark_client_id: str,
) -> list:
    """Erstelle echte Speaker-Profiles mit ONNX-Embeddings für Benchmark."""
    return await _create_enrolled_profiles(db_session, benchmark_client_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
class TestPipelineBenchmark:
    """
    Offizielle Pipeline mit echten Services (Gladia, ONNX, Sentinel, Mistral).
    Jeder Test führt _process_recording_pipeline() aus und verifiziert TIMING.
    """

    async def test_gladia_rate_constant(
        self,
        db_session: AsyncSession,
        benchmark_client_id: str,
        benchmark_meeting_id: str,
        enrolled_profiles: list,
        wav_short: bytes,
        caplog,
    ):
        """Gladia: ~17.8s (10-25s Range), konstant für 2-9 Min Audio."""
        import logging
        caplog.set_level(logging.INFO)

        file_key = f"benchmark/gladia_{uuid.uuid4().hex[:8]}.wav"
        await _upload_to_s3(wav_short, file_key)
        rid = await _create_recording(db_session, benchmark_client_id, benchmark_meeting_id, file_key)

        from app.tasks.transcription_tasks import _process_recording_pipeline
        start = time.time()
        try:
            await _process_recording_pipeline(rid, benchmark_client_id)
        except Exception as e:
            print(f"\n  Pipeline exception (non-fatal for benchmark): {type(e).__name__}: {e}")
        elapsed = time.time() - start

        timings = _parse_timing(caplog.text)
        gladia_s = timings.get("gladia_transcription", 0)
        num_segments = _parse_segments(caplog.text)

        print(f"\n  Gladia: {gladia_s:.2f}s ({num_segments} segments)")
        print(f"  Range: {RATE_GLADIA_RANGE[0]}-{RATE_GLADIA_RANGE[1]}s")
        print(f"  Gesamt: {elapsed:.2f}s")

        assert gladia_s > 0, "Gladia hat nicht gemessen"
        assert RATE_GLADIA_RANGE[0] <= gladia_s <= RATE_GLADIA_RANGE[1], (
            f"Gladia {gladia_s:.2f}s, erwartet {RATE_GLADIA_RANGE[0]}-{RATE_GLADIA_RANGE[1]}s"
        )

    async def test_speakerid_rate_with_profiles(
        self,
        db_session: AsyncSession,
        benchmark_client_id: str,
        benchmark_meeting_id: str,
        enrolled_profiles: list,
        wav_medium: bytes,
        caplog,
    ):
        """SpeakerID: ~0.476s/seg (0.2-1.0) mit 3 echten Profiles."""
        import logging
        caplog.set_level(logging.INFO)

        file_key = f"benchmark/speakerid_{uuid.uuid4().hex[:8]}.wav"
        await _upload_to_s3(wav_medium, file_key)
        rid = await _create_recording(db_session, benchmark_client_id, benchmark_meeting_id, file_key)

        from app.tasks.transcription_tasks import _process_recording_pipeline
        start = time.time()
        try:
            await _process_recording_pipeline(rid, benchmark_client_id)
        except Exception as e:
            print(f"\n  Pipeline exception (non-fatal for benchmark): {type(e).__name__}: {e}")
        elapsed = time.time() - start

        timings = _parse_timing(caplog.text)
        speakerid_s = timings.get("speaker_identification", 0)
        num_segments = _parse_segments(caplog.text)
        num_speakers = _parse_speakers(caplog.text)

        print(f"\n  SpeakerID: {speakerid_s:.2f}s / {num_segments} segs / {num_speakers} speakers")
        print(f"  Range: {RATE_SPEAKERID_RANGE[0]}-{RATE_SPEAKERID_RANGE[1]}s/seg")

        assert speakerid_s > 0, "SpeakerID hat nicht gemessen"
        assert num_segments > 0, "Keine Segmente"
        rate = speakerid_s / num_segments
        print(f"  Rate: {rate:.3f}s/seg")
        assert RATE_SPEAKERID_RANGE[0] <= rate <= RATE_SPEAKERID_RANGE[1], (
            f"SpeakerID rate {rate:.3f}s/seg, erwartet {RATE_SPEAKERID_RANGE[0]}-{RATE_SPEAKERID_RANGE[1]}"
        )

    async def test_onnx_rate_with_profiles(
        self,
        db_session: AsyncSession,
        benchmark_client_id: str,
        benchmark_meeting_id: str,
        enrolled_profiles: list,
        wav_medium: bytes,
        caplog,
    ):
        """ONNX: ~0.951s/seg (0.5-2.0) mit 3 echten Profiles."""
        import logging
        caplog.set_level(logging.INFO)

        file_key = f"benchmark/onnx_{uuid.uuid4().hex[:8]}.wav"
        await _upload_to_s3(wav_medium, file_key)
        rid = await _create_recording(db_session, benchmark_client_id, benchmark_meeting_id, file_key)

        from app.tasks.transcription_tasks import _process_recording_pipeline
        start = time.time()
        try:
            await _process_recording_pipeline(rid, benchmark_client_id)
        except Exception as e:
            print(f"\n  Pipeline exception (non-fatal for benchmark): {type(e).__name__}: {e}")
        elapsed = time.time() - start

        timings = _parse_timing(caplog.text)
        onnx_s = timings.get("onnx_segment_reassignment", 0)
        num_segments = _parse_segments(caplog.text)

        print(f"\n  ONNX: {onnx_s:.2f}s / {num_segments} segs")
        print(f"  Range: {RATE_ONNX_RANGE[0]}-{RATE_ONNX_RANGE[1]}s/seg")

        assert onnx_s > 0, "ONNX hat nicht gemessen"
        assert num_segments > 0, "Keine Segmente"
        rate = onnx_s / num_segments
        print(f"  Rate: {rate:.3f}s/seg")
        assert RATE_ONNX_RANGE[0] <= rate <= RATE_ONNX_RANGE[1], (
            f"ONNX rate {rate:.3f}s/seg, erwartet {RATE_ONNX_RANGE[0]}-{RATE_ONNX_RANGE[1]}"
        )

    async def test_sentinel_rate_per_chunk(
        self,
        db_session: AsyncSession,
        benchmark_client_id: str,
        benchmark_meeting_id: str,
        enrolled_profiles: list,
        wav_medium: bytes,
        caplog,
    ):
        """Sentinel: ~63.2s/chunk (30-120) — erfordert llama-cpp-python."""
        import logging
        caplog.set_level(logging.INFO)

        # Prüfe ob Sentinel LLM verfügbar ist
        try:
            from llama_cpp import Llama
        except ImportError:
            pytest.skip("llama-cpp-python not installed — Sentinel cannot run LLM")

        # Prüfe ob Modell existiert
        model_path = os.environ.get("SENTINEL_MODEL_PATH", "")
        if not os.path.exists(model_path):
            pytest.skip(f"Sentinel model not found at {model_path}")

        file_key = f"benchmark/sentinel_{uuid.uuid4().hex[:8]}.wav"
        await _upload_to_s3(wav_medium, file_key)
        rid = await _create_recording(db_session, benchmark_client_id, benchmark_meeting_id, file_key)

        from app.tasks.transcription_tasks import _process_recording_pipeline
        start = time.time()
        try:
            await _process_recording_pipeline(rid, benchmark_client_id)
        except Exception as e:
            print(f"\n  Pipeline exception (non-fatal for benchmark): {type(e).__name__}: {e}")
        elapsed = time.time() - start

        timings = _parse_timing(caplog.text)
        sentinel_s = timings.get("sentinel_llm", 0)
        num_chunks = _parse_chunks(caplog.text)

        print(f"\n  Sentinel: {sentinel_s:.2f}s / {num_chunks} chunks")
        print(f"  Range: {RATE_SENTINEL_RANGE[0]}-{RATE_SENTINEL_RANGE[1]}s/chunk")

        assert sentinel_s > 0, "Sentinel hat nicht gemessen"
        assert num_chunks > 0, "Keine Chunks verarbeitet"
        rate = sentinel_s / num_chunks
        print(f"  Rate: {rate:.1f}s/chunk")
        assert RATE_SENTINEL_RANGE[0] <= rate <= RATE_SENTINEL_RANGE[1], (
            f"Sentinel rate {rate:.1f}s/chunk, erwartet {RATE_SENTINEL_RANGE[0]}-{RATE_SENTINEL_RANGE[1]}"
        )

    async def test_pipeline_total(
        self,
        db_session: AsyncSession,
        benchmark_client_id: str,
        benchmark_meeting_id: str,
        enrolled_profiles: list,
        wav_medium: bytes,
        caplog,
    ):
        """Pipeline total: ~158s (ohne Sentinel) oder ~348s (mit Sentinel) für 9-Min Audio."""
        import logging
        caplog.set_level(logging.INFO)

        file_key = f"benchmark/total_{uuid.uuid4().hex[:8]}.wav"
        await _upload_to_s3(wav_medium, file_key)
        rid = await _create_recording(db_session, benchmark_client_id, benchmark_meeting_id, file_key)

        from app.tasks.transcription_tasks import _process_recording_pipeline
        start = time.time()
        try:
            await _process_recording_pipeline(rid, benchmark_client_id)
        except Exception as e:
            print(f"\n  Pipeline exception (non-fatal for benchmark): {type(e).__name__}: {e}")
        elapsed = time.time() - start

        timings = _parse_timing(caplog.text)
        num_segments = _parse_segments(caplog.text)
        num_chunks = _parse_chunks(caplog.text)
        sentinel_fallback = _sentinel_is_fallback(caplog.text)

        print(f"\n  Pipeline Total: {elapsed:.2f}s")
        if sentinel_fallback:
            print(f"  Sentinel: FALLBACK (kein llama-cpp-python)")
            print(f"  Range (ohne Sentinel): {PIPELINE_TOTAL_WITHOUT_SENTINEL[0]}-{PIPELINE_TOTAL_WITHOUT_SENTINEL[1]}s")
            total_range = PIPELINE_TOTAL_WITHOUT_SENTINEL
        else:
            print(f"  Range (mit Sentinel): {PIPELINE_TOTAL_WITH_SENTINEL[0]}-{PIPELINE_TOTAL_WITH_SENTINEL[1]}s")
            total_range = PIPELINE_TOTAL_WITH_SENTINEL

        print(f"  Segments: {num_segments}, Chunks: {num_chunks}")
        for stage, dur in sorted(timings.items()):
            print(f"    {stage}: {dur:.2f}s")

        assert total_range[0] <= elapsed <= total_range[1], (
            f"Pipeline {elapsed:.0f}s, erwartet {total_range[0]}-{total_range[1]}s"
        )
