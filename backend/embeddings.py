"""
Generate embeddings for event descriptions. Uses Gemini embedding API (free tier).
Required for vector search / Actian VectorAI track.
"""
from __future__ import annotations

from typing import Any

from config import GEMINI_API_KEY

_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float] | None:
    if not text or not GEMINI_API_KEY:
        return None
    if text in _cache:
        return _cache[text]
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        vec = result["embedding"]
        _cache[text] = vec
        return vec
    except Exception:
        return None


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
        except NotImplementedError:
            pass
    # When not using Actian, store.py already stores embedding_json in SQLite
