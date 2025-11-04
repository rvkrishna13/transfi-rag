"""
Core LLM client for query generation.
"""
import os
import asyncio
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Known pricing (USD per 1K tokens). Adjust as needed.
MODEL_PRICING = {
    # OpenAI examples (kept for reference)
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "o3-mini": {"input": 0.00055, "output": 0.0022},
    # Gemini examples (approx; update if needed)
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
}


class LLMClient:
    """Client for LLM generation using Gemini."""
    
    def __init__(self, model: str, api_key: str = None):
        self.model = model
        self._api_key = api_key or 'AIzaSyCjWg6C5Kl9aTq3GY0do4uJKg84_Tx7nao'
        self._token_encoder = None
        self._gemini_model = None

    async def ensure_clients(self) -> None:
        # Initialize token encoder once
        if self._token_encoder is None:
            try:
                import tiktoken  # type: ignore
            except Exception:
                self._token_encoder = None
            else:
                try:
                    self._token_encoder = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    self._token_encoder = None

        # Initialize Gemini client
        if self._gemini_model is None:
            try:
                import google.generativeai as genai  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "google-generativeai not installed. Please install it and set GOOGLE_API_KEY."
                ) from exc
            api_key = self._api_key or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY environment variable is not set.")
            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel(self.model)
            logger.info("Initialized Gemini model %s", self.model)

    def count_tokens(self, text: str) -> int:
        if self._token_encoder is None:
            # Fallback heuristic: ~4 chars per token
            return max(1, int(len(text) / 4))
        return len(self._token_encoder.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(self.model)
        if not pricing:
            return 0.0
        return (input_tokens / 1000.0) * pricing["input"] + (output_tokens / 1000.0) * pricing["output"]

    async def generate(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        await self.ensure_clients()
        assert self._gemini_model is not None

        # Gemini supports system instruction via model configuration; we include it in the content as well for clarity.
        full_prompt = f"System: {system_prompt}\n\n{user_prompt}"
        input_tokens = self.count_tokens(full_prompt)

        def call():
            return self._gemini_model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0,
                    "top_p": 1,
                    "top_k": 1,
                },
            )

        logger.info("LLM request started")
        resp = await asyncio.to_thread(call)
        content = getattr(resp, "text", None) or ""
        logger.info("LLM response received (%d chars)", len(content))

        # Try to use Gemini usage metadata if available
        output_tokens = 0
        try:
            usage = getattr(resp, "usage_metadata", None)
            if usage and getattr(usage, "candidates_token_count", None) is not None:
                output_tokens = int(usage.candidates_token_count)  # type: ignore
            elif usage and getattr(usage, "output_tokens", None) is not None:
                output_tokens = int(usage.output_tokens)  # type: ignore
            else:
                output_tokens = self.count_tokens(content)
        except Exception:
            output_tokens = self.count_tokens(content)

        return content, input_tokens, output_tokens

