"""Embedding Client — generate vector embeddings via OpenAI-compatible API.

Aligned with Execution Architecture §5.3 (Model Router — Embedding):
- Default: Qwen Embedding (compliant, low cost)
- Fallback: text-embedding-3-small

Usage::

    from ai_runtime.embedding import EmbeddingClient

    client = EmbeddingClient()
    vec = client.embed("友宝完成C轮融资")
    vecs = client.embed_batch(["文本1", "文本2"])
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI

from ai_runtime.cost_tracker import CostTracker
from utils.logger import get_logger

# Embedding model pricing (CNY per million tokens)
EMBEDDING_PRICING: dict[str, float] = {
    "text-embedding-3-small": 0.14,
    "text-embedding-3-large": 0.9,
    "qwen-embedding": 0.7,
    "bge-m3": 0.0,  # self-hosted
}


@dataclass
class EmbeddingResponse:
    """Result of an embedding call."""

    vectors: list[list[float]]
    model: str
    total_tokens: int = 0
    latency_ms: int = 0
    dimension: int = 0

    @property
    def count(self) -> int:
        return len(self.vectors)


class EmbeddingClient:
    """Generate embeddings via OpenAI-compatible API.

    Parameters
    ----------
    api_key / base_url:
        Override env vars ``LLM_API_KEY``, ``LLM_BASE_URL``.
    model:
        Embedding model name. Default from env ``EMBEDDING_MODEL``
        or ``text-embedding-3-small``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self.model = model or os.environ.get(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.max_retries = max_retries
        self.logger = get_logger()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def embed(self, text: str) -> list[float]:
        """Embed a single text. Returns vector."""
        resp = self.embed_batch([text])
        return resp.vectors[0]

    def embed_batch(self, texts: list[str]) -> EmbeddingResponse:
        """Embed a batch of texts. Returns EmbeddingResponse."""
        if not texts:
            return EmbeddingResponse(vectors=[], model=self.model)

        # Clean texts (API rejects empty strings)
        cleaned = [t.strip() or " " for t in texts]

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._call(cleaned)
            except Exception as e:
                last_error = e
                wait = 2**attempt
                self.logger.warning(
                    "[embedding] attempt %d failed: %s, retry in %ds",
                    attempt + 1, e, wait,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Embedding failed after {self.max_retries} retries: {last_error}")

    def _call(self, texts: list[str]) -> EmbeddingResponse:
        """Internal API call."""
        start = time.time()

        response = self._client.embeddings.create(
            model=self.model,
            input=texts,
        )

        latency_ms = int((time.time() - start) * 1000)
        vectors = [item.embedding for item in response.data]
        total_tokens = response.usage.total_tokens if response.usage else 0
        dimension = len(vectors[0]) if vectors else 0

        # Track cost
        price_per_m = EMBEDDING_PRICING.get(self.model, 0.5)
        cost = total_tokens / 1_000_000 * price_per_m

        self.logger.info(
            "[embedding] model=%s count=%d tokens=%d dim=%d latency=%dms",
            self.model, len(texts), total_tokens, dimension, latency_ms,
        )

        return EmbeddingResponse(
            vectors=vectors,
            model=self.model,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            dimension=dimension,
        )
