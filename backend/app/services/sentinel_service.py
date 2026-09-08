import gc
import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import List, Dict, Any
try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

MIN_MODEL_SIZE = 900 * 1024 * 1024   # 900 MB
MAX_MODEL_SIZE = 1500 * 1024 * 1024   # 1.5 GB
DOWNLOAD_TIMEOUT = 300  # seconds


def _download_model(model_url: str, model_path: str) -> bool:
    """Download model from SENTINEL_MODEL_URL with atomic rename and size sanity check."""
    import urllib.request
    import tempfile

    model_dir = os.path.dirname(model_path)
    os.makedirs(model_dir, exist_ok=True)

    tmp_path = model_path + ".tmp"
    try:
        logger.info(f"Sentinel: downloading model from {model_url} ...")
        urllib.request.urlretrieve(model_url, tmp_path)

        file_size = os.path.getsize(tmp_path)
        if file_size < MIN_MODEL_SIZE or file_size > MAX_MODEL_SIZE:
            logger.warning(
                f"Sentinel: downloaded model has unexpected size {file_size} bytes "
                f"(expected {MIN_MODEL_SIZE}-{MAX_MODEL_SIZE}). Removing."
            )
            os.remove(tmp_path)
            return False

        os.rename(tmp_path, model_path)
        logger.info(f"Sentinel: model downloaded successfully ({file_size} bytes).")
        return True
    except Exception as e:
        logger.warning(f"Sentinel: download failed: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


class SentinelService:
    """
    Local SLM (Small Language Model) Service for high-speed semantic analysis.
    Uses Qwen2.5-1.5B (GGUF) via llama-cpp-python.
    Purpose: Semantic boundary detection and low-latency chunk summarization.
    """

    def __init__(self, model_path: str = "/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"):
        self.model_path = model_path
        self.llm = None
        self._semaphore = asyncio.Semaphore(2)

        if Llama is None:
            logger.warning("llama-cpp-python not installed. SentinelService will operate in fallback mode.")
            return

        if not os.path.exists(self.model_path):
            model_url = os.environ.get("SENTINEL_MODEL_URL", "")
            if not model_url:
                logger.warning(
                    f"Sentinel Model not found at {self.model_path} and "
                    "SENTINEL_MODEL_URL not set. Fallback active."
                )
                return

            with ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    future = pool.submit(_download_model, model_url, self.model_path)
                    success = future.result(timeout=DOWNLOAD_TIMEOUT)
                except FuturesTimeoutError:
                    logger.warning(
                        f"Sentinel: download timed out after {DOWNLOAD_TIMEOUT}s. Fallback active."
                    )
                    success = False
                except Exception as e:
                    logger.warning(f"Sentinel: download error: {e}. Fallback active.")
                    success = False

            if not success:
                return

        try:
            import time
            cold_start = time.time()
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=1024,
                n_threads=2,
                verbose=False
            )
            cold_start_duration = time.time() - cold_start
            logger.info(f"TIMING: sentinel_cold_start duration={cold_start_duration:.2f}s model={self.model_path}")
            logger.info("Sentinel (Qwen-1.5B) initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to load Sentinel LLM: {e}")

    async def detect_boundaries(self, text: str) -> List[str]:
        """Splits a long transcript into semantic chapters."""
        if not self.llm:
            # Fallback to simple logic if model is missing
            return [text[i:i+2000] for i in range(0, len(text), 2000)]
            
        prompt = f"<|im_start|>system\nYou are a semantic segmenter. Split the following meeting transcript into logical chapters. Return each chapter separated by '---'.<|im_end|>\n<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.llm(prompt, max_tokens=512, stop=["<|im_end|>"]))
            
        output = response["choices"][0]["text"]
        return [s.strip() for s in output.split("---") if s.strip()]

    async def summarize_chunk(self, chunk: str, lang: str = "fr") -> str:
        """Rapidly synthesizes a 5-minute chunk (MAP phase)."""
        if not self.llm:
            # Fallback: Preserve full text with speaker info intact
            # CRITICAL: Do NOT truncate speaker names - Mistral needs them for assignee resolution
            import re
            # Extract and preserve all speaker mentions
            speaker_pattern = re.compile(r'(Speaker \d+|[A-Z][a-z]+ [A-Z][a-z]+)')
            speakers_found = speaker_pattern.findall(chunk)
            speaker_header = f"[Speakers detected: {', '.join(set(speakers_found))}]\n" if speakers_found else ""
            return speaker_header + chunk[:1500] + "..." if len(chunk) > 1500 else chunk
            
        prompt = f"<|im_start|>system\nSummarize this meeting segment in 2-3 sentences. CRITICAL: Preserve speaker names exactly as written (e.g. 'Ahmed proposed X', 'Fatima agreed'). Do NOT merge speakers or use generic terms like 'the team'. Language: {lang}<|im_end|>\n<|im_start|>user\n{chunk}<|im_end|>\n<|im_start|>assistant\n"
        
        async with self._semaphore:
            import time
            llm_start = time.time()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.llm(prompt, max_tokens=128))
            llm_dur = time.time() - llm_start
            usage = response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            tok_per_sec = completion_tokens / llm_dur if llm_dur > 0 else 0
            logger.info(f"TIMING: sentinel_summarize prompt_tokens={prompt_tokens} output_tokens={completion_tokens} llm_dur={llm_dur:.2f}s tok_per_sec={tok_per_sec:.1f}")

        return response["choices"][0]["text"].strip()

# Eager singleton: load Qwen-1.5B at first access to avoid cold-start latency
_sentinel_instance: SentinelService | None = None
_sentinel_loaded: bool = False


def get_sentinel_service() -> SentinelService:
    """Return the singleton SentinelService, creating it on first call.

    The model is loaded once on first ``summarize_chunk`` call and reused.
    Cold-start is logged explicitly for observability.
    """
    global _sentinel_instance, _sentinel_loaded
    if _sentinel_instance is None:
        import time
        load_start = time.time()
        logger.info("Sentinel: loading Qwen-1.5B model (cold start)...")
        _sentinel_instance = SentinelService()
        load_dur = time.time() - load_start
        _sentinel_loaded = True
        if _sentinel_instance.llm is not None:
            logger.info(f"TIMING: sentinel_preload duration={load_dur:.2f}s status=loaded")
        else:
            logger.warning(f"TIMING: sentinel_preload duration={load_dur:.2f}s status=fallback")
    return _sentinel_instance


def reset_sentinel() -> None:
    """Release the SentinelService singleton and its LLM memory."""
    global _sentinel_instance
    if _sentinel_instance is not None:
        if hasattr(_sentinel_instance, "llm") and _sentinel_instance.llm is not None:
            del _sentinel_instance.llm
        _sentinel_instance = None
        gc.collect()
