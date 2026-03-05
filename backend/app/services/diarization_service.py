import logging
import os
import subprocess
import tempfile
from typing import List, Dict, Any

try:
    import torch
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)

class DiarizationService:
    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        """
        Singleton initialization of the pyannote pipeline to save memory.
        Loads once when the Celery worker starts processing its first diarization task.
        """
        if not PYANNOTE_AVAILABLE:
            logger.warning("pyannote.audio is not installed. Diarization will be disabled.")
            return None
            
        if cls._pipeline is None:
            logger.info("Initializing pyannote.audio pipeline...")
            token = getattr(settings, "HUGGINGFACE_TOKEN", None)
            if not token:
                logger.error("HUGGINGFACE_TOKEN is missing in settings. Cannot initialize diarization.")
                return None
                
            try:
                # Load pipeline from HuggingFace
                cls._pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=token
                )
                
                # Check for CUDA GPU availability
                if torch.cuda.is_available():
                    logger.info("CUDA is available. Moving pipeline to GPU.")
                    cls._pipeline.to(torch.device("cuda"))
                else:
                    logger.warning("CUDA not available. Running pyannote on CPU (this might be very slow).")
            except Exception as e:
                logger.error(f"Failed to initialize diarization pipeline: {e}")
                cls._pipeline = None
                
        return cls._pipeline

    @classmethod
    def resample_audio(cls, input_path: str, output_path: str) -> bool:
        """
        Resamples audio to 16kHz mono using FFmpeg (recommended for pyannote).
        """
        try:
            logger.info(f"Resampling audio from {input_path} to {output_path} (16kHz, mono)")
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "16000", output_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg resampling failed: {e}")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found on the system.")
            return False

    @classmethod
    async def diarize(cls, audio_file_path: str) -> List[Dict[str, Any]]:
        """
        Runs speaker diarization on audio bytes.
        Returns a list of segments: [{"speaker": "SPEAKER_00", "start": 12.3, "end": 15.7}, ...]
        """
        pipeline = cls.get_pipeline()
        
        if pipeline is None:
            logger.warning("Pipeline is not initialized. Skipping diarization.")
            return []
            
        input_path = audio_file_path
            
        resampled_path = f"{input_path}_16k.wav"
        
        try:
            # Resample audio
            if not cls.resample_audio(input_path, resampled_path):
                logger.warning("Resampling failed, falling back to original audio for diarization.")
                audio_to_process = input_path
            else:
                audio_to_process = resampled_path
                
            logger.info(f"Starting diarization for {audio_file_path}")
            
            # Run inference
            diarization = pipeline(audio_to_process)
            
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": round(turn.start, 2),
                    "end": round(turn.end, 2)
                })
            
            logger.info(f"Diarization completed. Found {len(segments)} segments.")
            return segments
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.error("Out of Memory (OOM) error during diarization.")
            else:
                logger.error(f"RuntimeError during diarization: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during diarization: {e}")
            return []
        finally:
            # Cleanup temp files (only internally created resampled_path)
            if os.path.exists(resampled_path):
                os.remove(resampled_path)
            
            # Clean up GPU memory
            if PYANNOTE_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
