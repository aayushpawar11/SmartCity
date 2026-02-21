"""
Semantic search over events: "Show me all accidents involving trucks."
Uses Actian VectorAI when configured; otherwise SQLite + in-memory similarity.
"""
from __future__ import annotations

import math
from typing import Any

from config import ACTIAN_ENABLED
from embeddings import get_embedding


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def search_events(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []

    if ACTIAN_ENABLED:
        try:
            from actian_adapter import search_actian

            return search_actian(query_embedding, top_k=top_k)
        except NotImplementedError:
            pass

    # Fallback: load events with embeddings from SQLite and rank by similarity
    from store import get_events_with_embeddings

    events = get_events_with_embeddings(limit=500)
    scored = []
    for ev in events:
        emb = ev.get("embedding")
        if not emb:
            continue
        sim = _cosine_sim(query_embedding, emb)
        scored.append((sim, ev))
    scored.sort(key=lambda x: -x[0])
    return [ev for _, ev in scored[:top_k]]
