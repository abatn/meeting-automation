import asyncio
import logging
import os
import struct
import time
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "speaker_embeddings")
ONNX_MODEL_PATH = os.path.join(MODEL_DIR, "ecapa-speaker-v1.onnx")
FBANK_FILTER_PATH = os.path.join(MODEL_DIR, "fbank-80x201-f32.bin")

EMBEDDING_DIM = 192
SAMPLE_RATE = 16000
FBANK_NUM_FILTERS = 80
FBANK_FRAME_LENGTH = 25.0  # ms
FBANK_FRAME_SHIFT = 10.0  # ms


class SpeakerEmbeddingService:
    """
    Lightweight speaker embedding extraction using ONNX Runtime.
    No PyTorch dependency — runs on CPU with ~80 MB model size.

    Model: speechbrain/spkrec-ecapa-voxceleb (ONNX converted)
    Output: 192-dim embedding vector per audio segment
    """

    _instance: Optional["SpeakerEmbeddingService"] = None
    _initialized: bool = False
    _instance_lock = asyncio.Lock()

    def __init__(self):
        self._session = None
        self._fbank_filters = None
        self._available = False

    @classmethod
    async def get_instance(cls) -> "SpeakerEmbeddingService":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                await cls._instance.initialize()
            return cls._instance

    async def initialize(self) -> bool:
        """Load ONNX model and fbank filters. Returns True if successful."""
        if self._initialized:
            return self._available

        try:
            import onnxruntime as ort

            if not os.path.exists(ONNX_MODEL_PATH):
                logger.error(f"ONNX model not found at {ONNX_MODEL_PATH}")
                self._available = False
                return False

            providers = ["CPUExecutionProvider"]
            self._session = ort.InferenceSession(ONNX_MODEL_PATH, providers=providers)
            logger.info(f"ONNX model loaded: {self._session.get_inputs()[0].name} -> {self._session.get_outputs()[0].name}")

            self._fbank_filters = self._load_fbank_filters()
            if self._fbank_filters is None:
                self._available = False
                return False

            self._initialized = True
            self._available = True
            logger.info("SpeakerEmbeddingService initialized successfully")
            return True

        except ImportError:
            logger.error("onnxruntime not installed — speaker embedding unavailable")
            self._available = False
            return False
        except Exception as e:
            logger.error(f"Failed to initialize SpeakerEmbeddingService: {e}")
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def _load_fbank_filters(self) -> Optional[np.ndarray]:
        """Load SpeechBrain-compatible fbank filter matrix (80x201 float32)."""
        try:
            if not os.path.exists(FBANK_FILTER_PATH):
                logger.error(f"fbank filter not found at {FBANK_FILTER_PATH}")
                return None

            with open(FBANK_FILTER_PATH, "rb") as f:
                data = f.read()

            num_values = len(data) // 4
            filters = np.array(struct.unpack(f"{num_values}f", data), dtype=np.float32)
            filters = filters.reshape(FBANK_NUM_FILTERS, -1)
            logger.info(f"fbank filters loaded: {filters.shape}")
            return filters
        except Exception as e:
            logger.error(f"Failed to load fbank filters: {e}")
            return None

    def _extract_fbank_features(self, audio: np.ndarray) -> np.ndarray:
        """
        Extract fbank features from raw audio, matching SpeechBrain preprocessing.
        Uses the loaded filter matrix for compatibility with the ONNX model.

        Args:
            audio: Raw audio array (16kHz, mono), shape (samples,)

        Returns:
            Log-filterbank features, shape (frames, 80)
        """
        audio = audio.astype(np.float32)

        if audio.ndim == 1:
            audio = audio[np.newaxis, :]

        n_samples = audio.shape[1]
        frame_length = int(SAMPLE_RATE * FBANK_FRAME_LENGTH / 1000.0)
        frame_shift = int(SAMPLE_RATE * FBANK_FRAME_SHIFT / 1000.0)

        n_frames = 1 + (n_samples - frame_length) // frame_shift
        if n_frames <= 0:
            n_frames = 1

        features = np.zeros((n_frames, FBANK_NUM_FILTERS), dtype=np.float32)

        for i in range(n_frames):
            start = i * frame_shift
            end = min(start + frame_length, n_samples)
            frame = audio[0, start:end]

            if len(frame) < frame_length:
                frame = np.pad(frame, (0, frame_length - len(frame)), mode="constant")

            window = np.hamming(frame_length)
            frame = frame * window

            spectrum = np.abs(np.fft.rfft(frame, n=2 * (frame_length // 2 + 1)))
            spectrum = spectrum[: len(self._fbank_filters[0])]

            log_energy = np.log(np.dot(self._fbank_filters, spectrum) + 1e-30)
            features[i] = log_energy

        mean = np.mean(features, axis=0, keepdims=True)
        std = np.std(features, axis=0, keepdims=True) + 1e-10
        features = (features - mean) / std

        return features

    async def extract_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """
        Extract a 192-dim speaker embedding from an audio file.

        Args:
            audio_path: Path to audio file (any format, will be resampled to 16kHz mono)

        Returns:
            192-dim numpy array or None if extraction fails
        """
        if not self._initialized:
            await self.initialize()
        if not self._available:
            logger.warning("SpeakerEmbeddingService not available — returning None")
            return None

        try:
            import librosa

            audio, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

            if len(audio) < SAMPLE_RATE:
                logger.warning(f"Audio too short for embedding: {len(audio)} samples (< {SAMPLE_RATE})")
                return None

            features = self._extract_fbank_features(audio)

            input_names = [inp.name for inp in self._session.get_inputs()]
            features_expanded = features[np.newaxis, ...].astype(np.float32)
            feature_lens = np.array([features.shape[0]], dtype=np.float32)

            input_feed = {"features": features_expanded, "feature_lens": feature_lens}
            for name in input_names:
                if name not in input_feed:
                    logger.warning(f"Unexpected input name: {name}")

            result = self._session.run(None, input_feed)
            embedding = result[0].squeeze()

            if embedding.shape[0] != EMBEDDING_DIM:
                logger.error(f"Unexpected embedding dimension: {embedding.shape}, expected {EMBEDDING_DIM}")
                return None

            embedding = embedding / (np.linalg.norm(embedding) + 1e-10)

            logger.info(f"Embedding extracted: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")
            return embedding

        except ImportError:
            logger.error("librosa not installed — cannot extract embedding")
            return None
        except Exception as e:
            logger.error(f"Failed to extract embedding from {audio_path}: {e}")
            return None

    async def extract_embedding_from_bytes(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """
        Extract embedding from raw audio bytes (in-memory).

        Args:
            audio_bytes: Audio file content (WAV, MP3, etc.)

        Returns:
            192-dim numpy array or None
        """
        if not self._initialized:
            await self.initialize()
        if not self._available:
            return None

        try:
            import librosa
            import io

            audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=SAMPLE_RATE, mono=True)

            if len(audio) < SAMPLE_RATE:
                return None

            features = self._extract_fbank_features(audio)
            features_expanded = features[np.newaxis, ...].astype(np.float32)
            feature_lens = np.array([features.shape[0]], dtype=np.float32)
            input_feed = {"features": features_expanded, "feature_lens": feature_lens}
            result = self._session.run(None, input_feed)
            embedding = result[0].squeeze()

            if embedding.shape[0] != EMBEDDING_DIM:
                return None

            embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
            return embedding

        except Exception as e:
            logger.error(f"Failed to extract embedding from bytes: {e}")
            return None


speaker_embedding_service = SpeakerEmbeddingService()
