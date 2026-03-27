import logging
import os
import asyncio
from typing import List, Dict, Any
try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

class SentinelService:
    """
    Local SLM (Small Language Model) Service for high-speed semantic analysis.
    Uses Qwen2.5-1.5B (GGUF) via llama-cpp-python.
    Purpose: Semantic boundary detection and low-latency chunk summarization.
    """
    
    def __init__(self, model_path: str = "/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"):
        self.model_path = model_path
        self.llm = None
        self._lock = asyncio.Lock()
        
        if Llama is None:
            logger.warning("llama-cpp-python not installed. SentinelService will operate in fallback mode.")
        elif not os.path.exists(self.model_path):
            logger.warning(f"Sentinel Model not found at {self.model_path}. Fallback active.")
        else:
            try:
                # Optimized for 2GB RAM environment
                self.llm = Llama(
                    model_path=self.model_path,
                    n_ctx=2048,
                    n_threads=2,
                    verbose=False
                )
                logger.info("Sentinel (Qwen-1.5B) initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to load Sentinel LLM: {e}")

    async def detect_boundaries(self, text: str) -> List[str]:
        """Splits a long transcript into semantic chapters."""
        if not self.llm:
            # Fallback to simple logic if model is missing
            return [text[i:i+2000] for i in range(0, len(text), 2000)]
            
        prompt = f"<|im_start|>system\nYou are a semantic segmenter. Split the following meeting transcript into logical chapters. Return each chapter separated by '---'.<|im_end|>\n<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        
        async with self._lock:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.llm(prompt, max_tokens=512, stop=["<|im_end|>"]))
            
        output = response["choices"][0]["text"]
        return [s.strip() for s in output.split("---") if s.strip()]

    async def summarize_chunk(self, chunk: str, lang: str = "fr") -> str:
        """Rapidly synthesizes a 5-minute chunk (MAP phase)."""
        if not self.llm:
            return chunk[:500] + "..."
            
        prompt = f"<|im_start|>system\nSummarize this meeting segment in 2-3 sentences. Language: {lang}<|im_end|>\n<|im_start|>user\n{chunk}<|im_end|>\n<|im_start|>assistant\n"
        
        async with self._lock:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.llm(prompt, max_tokens=256))
            
        return response["choices"][0]["text"].strip()

sentinel = SentinelService()
