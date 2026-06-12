import asyncio
import logging
import os
import tempfile
from typing import Dict, List, Optional

import numpy as np

from app.services.speaker_embedding_service import speaker_embedding_service

logger = logging.getLogger(__name__)

MIN_SEGMENT_DURATION = 3.0  # Minimum seconds for reliable embedding
MIN_AUDIO_DURATION = 5.0    # Minimum total seconds per speaker


class AudioSegmentService:
    """
    Extracts audio segments per speaker from a full recording file
    using Gladia diarization timestamps.
    Uses ffmpeg (already in Docker image) for extraction.
    """

    async def extract_speaker_segments(
        self,
        audio_file_path: str,
        segments: List[Dict],
    ) -> Dict[str, str]:
        """
        Extract audio segments for each unique speaker.

        Args:
            audio_file_path: Path to the full audio file
            segments: Gladia diarization segments with speaker, start, end

        Returns:
            Dict mapping speaker label to temp file path, e.g.:
            {"Speaker 0": "/tmp/speaker_0.wav", ...}
        """
        speaker_segments = self._group_by_speaker(segments)
        result = {}

        async def extract_single(speaker_label: str, segs: List[Dict]) -> tuple:
            total_duration = sum(s["end"] - s["start"] for s in segs)
            if total_duration < MIN_AUDIO_DURATION:
                return speaker_label, None
            if len(segs) == 1:
                segment_path = await self._extract_single_segment(audio_file_path, segs[0])
            else:
                segment_path = await self._concatenate_segments(audio_file_path, segs)
            return speaker_label, segment_path

        tasks = [extract_single(label, segs) for label, segs in speaker_segments.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Speaker extraction failed: {res}")
                continue
            label, path = res
            if path and os.path.exists(path):
                result[label] = path
                total_duration = sum(s["end"] - s["start"] for s in speaker_segments[label])
                logger.info(f"Extracted {label}: {total_duration:.1f}s total audio")

        return result

    def _group_by_speaker(self, segments: List[Dict]) -> Dict[str, List[Dict]]:
        """Group segments by speaker label."""
        grouped = {}
        for seg in segments:
            speaker = seg.get("speaker", "Unknown")
            if speaker not in grouped:
                grouped[speaker] = []
            grouped[speaker].append(seg)
        return grouped

    async def _extract_single_segment(
        self, audio_file_path: str, segment: Dict
    ) -> Optional[str]:
        """Extract a single audio segment using ffmpeg."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()

        start = segment["start"]
        duration = segment["end"] - segment["start"]

        cmd = [
            "ffmpeg", "-y", "-i", audio_file_path,
            "-ss", str(start),
            "-t", str(duration),
            "-ar", "16000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            tmp.name,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"ffmpeg failed: {stderr.decode()}")
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)
                return None

            return tmp.name

        except Exception as e:
            logger.error(f"Failed to extract segment: {e}")
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
            return None

    async def _concatenate_segments(
        self, audio_file_path: str, segments: List[Dict]
    ) -> Optional[str]:
        """Extract and concatenate multiple segments for a speaker."""
        import shutil
        tmp_dir = tempfile.mkdtemp()
        part_files = []

        try:
            async def extract_part(i: int, seg: Dict) -> Optional[str]:
                duration = seg["end"] - seg["start"]
                if duration < 0.5:
                    return None
                part_path = os.path.join(tmp_dir, f"part_{i}.wav")
                cmd = [
                    "ffmpeg", "-y", "-i", audio_file_path,
                    "-ss", str(seg["start"]),
                    "-t", str(duration),
                    "-ar", "16000",
                    "-ac", "1",
                    "-acodec", "pcm_s16le",
                    part_path,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0 and os.path.exists(part_path):
                    return part_path
                return None

            tasks = [extract_part(i, seg) for i, seg in enumerate(segments)]
            results = await asyncio.gather(*tasks)
            part_files = [r for r in results if r is not None]

            if not part_files:
                return None

            if len(part_files) == 1:
                return part_files[0]

            concat_file = os.path.join(tmp_dir, "concat_list.txt")
            with open(concat_file, "w") as f:
                for pf in part_files:
                    f.write(f"file '{pf}'\n")

            output_path = os.path.join(tmp_dir, "speaker_combined.wav")
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-ar", "16000",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0 and os.path.exists(output_path):
                return output_path

            return None

        except Exception as e:
            logger.error(f"Failed to concatenate segments: {e}")
            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None

    async def extract_embeddings(
        self,
        speaker_segments: Dict[str, str],
    ) -> Dict[str, Optional[np.ndarray]]:
        """
        Extract speaker embeddings from audio segment files.

        Args:
            speaker_segments: Dict mapping speaker label to audio file path

        Returns:
            Dict mapping speaker label to embedding (or None if extraction failed)
        """
        embeddings = {}

        for speaker_label, audio_path in speaker_segments.items():
            embedding = await speaker_embedding_service.extract_embedding(audio_path)
            embeddings[speaker_label] = embedding

            if embedding is not None:
                logger.info(f"Embedding extracted for {speaker_label}")
            else:
                logger.warning(f"Failed to extract embedding for {speaker_label}")

            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        return embeddings

    async def cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary audio files."""
        for path in file_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup {path}: {e}")


audio_segment_service = AudioSegmentService()
