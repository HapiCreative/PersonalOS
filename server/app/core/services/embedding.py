"""
Embedding service with flexible provider support (Section 7).
Phase 3: Integrates with vector search for hybrid retrieval.
Provider is configurable — not hardcoded to one vendor.
"""

import hashlib
import logging
from abc import ABC, abstractmethod

from server.app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers. Extend for OpenAI, Cohere, local models, etc."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts. Returns list of 1536-dim vectors."""
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...


class NoOpEmbeddingProvider(EmbeddingProvider):
    """
    No-op provider for when no LLM API key is configured.
    Returns None-equivalent signals so the system degrades gracefully
    to full-text-only search.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        logger.warning("NoOpEmbeddingProvider: No embeddings generated. Configure an embedding provider.")
        return []

    async def embed_single(self, text: str) -> list[float]:
        logger.warning("NoOpEmbeddingProvider: No embedding generated. Configure an embedding provider.")
        return []


# Global provider instance — set at startup or via configuration
_provider: EmbeddingProvider = NoOpEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Get the current embedding provider."""
    return _provider


def set_embedding_provider(provider: EmbeddingProvider) -> None:
    """Set the embedding provider (call at app startup)."""
    global _provider
    _provider = provider


async def generate_embedding(text: str) -> list[float] | None:
    """
    Generate an embedding for a single text.
    Returns None if the provider is not configured or fails.
    """
    provider = get_embedding_provider()
    if isinstance(provider, NoOpEmbeddingProvider):
        return None
    try:
        return await provider.embed_single(text)
    except Exception:
        logger.exception("Failed to generate embedding")
        return None


async def generate_embeddings(texts: list[str]) -> list[list[float] | None]:
    """
    Generate embeddings for multiple texts.
    Returns a list where each element is either the embedding or None on failure.
    """
    provider = get_embedding_provider()
    if isinstance(provider, NoOpEmbeddingProvider):
        return [None] * len(texts)
    try:
        results = await provider.embed(texts)
        # Pad with None if provider returned fewer results
        while len(results) < len(texts):
            results.append(None)  # type: ignore
        return results  # type: ignore
    except Exception:
        logger.exception("Failed to generate embeddings")
        return [None] * len(texts)


def compute_checksum(content: str) -> str:
    """Compute a SHA-256 checksum for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
