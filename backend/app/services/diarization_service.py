"""
Diarization Service for speaker separation.

This service uses pyannote.audio or similar for speaker diarization.
Currently implemented as a placeholder that can be extended.
"""
import logging
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class DiarizationService:
    """
    Service for audio diarization (speaker separation).
    """

    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        """Get or initialize diarization pipeline."""
        if cls._pipeline is None:
            try:
                from pyannote.audio import Pipeline
                # Use pretrained model (requires huggingface-hub authentication)
                cls._pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=True
                )
            except ImportError:
                logger.warning("pyannote.audio not installed. Diarization disabled.")
                cls._pipeline = None
            except Exception as e:
                logger.error(f"Failed to load diarization pipeline: {e}")
                cls._pipeline = None
        return cls._pipeline

    @classmethod
    async def diarize(cls, audio_path: str) -> List[Dict]:
        """
        Perform diarization on an audio file.

        Args:
            audio_path: Path to the audio file

        Returns:
            List of segments with speaker labels: [{"speaker": "SPEAKER_00", "start": 0.0, "end": 2.5}, ...]
        """
        pipeline = cls.get_pipeline()
        if not pipeline:
            return []

        try:
            # Run diarization
            diarization = pipeline(audio_path)

            # Convert to simple list format
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": turn.start,
                    "end": turn.end
                })

            return segments
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return []

    @classmethod
    def resample_audio(cls, audio_path: str, target_sr: int = 16000) -> bool:
        """
        Resample audio to target sample rate (required for diarization).
        Returns True if successful.
        """
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            audio = audio.set_frame_rate(target_sr)
            audio.export(audio_path, format="wav")
            return True
        except ImportError:
            logger.warning("pydub not installed. Audio resampling skipped.")
            return True  # Assume it's fine
        except Exception as e:
            logger.error(f"Audio resampling failed: {e}")
            return False
