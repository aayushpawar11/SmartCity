"""
Generate embeddings for event/incident descriptions.
Uses Gemini embedding API. Required for vector search / Actian VectorAI.
"""
from __future__ import annotations

import logging
from typing import Any

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 3072
_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float] | None:
    """Get embedding vector from Gemini. Returns None on failure."""
    if not text or not GEMINI_API_KEY:
        return None
    if text in _cache:
        return _cache[text]
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        vec = result["embedding"]
        _cache[text] = vec
        return vec
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        return None


def build_incident_text(metadata: dict) -> str:
    """Convert structured incident metadata into a searchable text string for embedding."""
    parts = []
    if metadata.get("event_type"):
        parts.append(metadata["event_type"])
    if metadata.get("severity"):
        parts.append(f"{metadata['severity']} severity")
    if metadata.get("vehicles_detected"):
        parts.append(f"{metadata['vehicles_detected']} vehicles")
    if metadata.get("blocked_lanes"):
        parts.append(f"{metadata['blocked_lanes']} blocked lanes")
    if metadata.get("confidence"):
        parts.append(f"confidence {metadata['confidence']:.2f}")
    if metadata.get("description"):
        parts.append(metadata["description"])
    return " ".join(parts) if parts else "traffic incident"


def generate_embedding(text: str) -> list[float]:
    """Wrapper around get_embedding that guarantees a fixed-length vector.
    Returns a zero vector as fallback so the pipeline never breaks."""
    vec = get_embedding(text)
    if vec and len(vec) == EMBEDDING_DIM:
        return vec
    if vec:
        # Pad or truncate to fixed dimension
        if len(vec) < EMBEDDING_DIM:
            vec.extend([0.0] * (EMBEDDING_DIM - len(vec)))
        return vec[:EMBEDDING_DIM]
    logger.warning("Using zero-vector fallback for: %s", text[:80])
    return [0.0] * EMBEDDING_DIM


def embed_and_store(event_id: str, description: str, metadata: dict[str, Any]) -> None:
    """Store embedding in Actian when enabled; otherwise caller stores in SQLite."""
    from config import ACTIAN_ENABLED

    vec = get_embedding(description)
    if not vec:
        return
    if ACTIAN_ENABLED:
        try:
            from actian_adapter import insert_embedding_actian

            insert_embedding_actian(event_id, vec, metadata)
        except (NotImplementedError, Exception) as e:
            logger.warning("Actian embed_and_store fallback: %s", e)
