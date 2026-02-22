"""
Generate embeddings for event/incident descriptions.
Uses Gemini REST API directly (no SDK needed). Required for vector search / Actian VectorAI.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com"
EMBEDDING_MODELS = ["gemini-embedding-001", "embedding-001", "text-embedding-004"]
EMBEDDING_DIM = 3072
_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float] | None:
    """Get embedding vector from Gemini REST API. Returns None on failure."""
    if not text or not GEMINI_API_KEY:
        return None
    if text in _cache:
        return _cache[text]
    for model in EMBEDDING_MODELS:
        for version in ("v1beta", "v1"):
            try:
                url = f"{GEMINI_BASE}/{version}/models/{model}:embedContent?key={GEMINI_API_KEY}"
                payload = {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": "RETRIEVAL_DOCUMENT",
                }
                resp = httpx.post(url, json=payload, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    vec = data["embedding"]["values"]
                    _cache[text] = vec
                    logger.info("Embedding OK via %s/%s", version, model)
                    return vec
            except Exception:
                continue
    logger.warning("All embedding models failed for: %s", text[:60])
    return None


def build_incident_text(metadata: dict) -> str:
    """Convert structured incident metadata into a searchable text string for embedding."""
    parts = []
    if metadata.get("event_type"):
        parts.append(metadata["event_type"])
    if metadata.get("rating"):
        parts.append(f"rating {metadata['rating']}/10")
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
