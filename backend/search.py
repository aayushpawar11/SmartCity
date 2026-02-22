"""
Semantic search, clearance estimation, and false-positive detection.
Uses Actian VectorAI when configured; otherwise SQLite + in-memory similarity.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from config import ACTIAN_ENABLED
from embeddings import get_embedding

logger = logging.getLogger(__name__)

DEFAULT_CLEARANCE_MINUTES = 15.0
FALSE_POSITIVE_THRESHOLD = 0.4


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def search_events(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Semantic search over legacy events table."""
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []

    if ACTIAN_ENABLED:
        try:
            from actian_adapter import search_actian
            return search_actian(query_embedding, top_k=top_k)
        except (NotImplementedError, Exception):
            pass

    from store import get_events_with_embeddings
    events = await get_events_with_embeddings(limit=500)
    scored = []
    for ev in events:
        emb = ev.get("embedding")
        if not emb:
            continue
        sim = _cosine_sim(query_embedding, emb)
        scored.append((sim, ev))
    scored.sort(key=lambda x: -x[0])
    return [ev for _, ev in scored[:top_k]]


def estimate_clearance(similar_incidents: list[dict]) -> float:
    """Estimate clearance time in minutes from similar past incidents.
    Averages clearance_minutes from metadata; returns default if no data."""
    clearance_values = []
    for inc in similar_incidents:
        meta = inc.get("metadata", {})
        ct = meta.get("clearance_minutes")
        if ct and ct > 0:
            clearance_values.append(ct)

    if not clearance_values:
        return DEFAULT_CLEARANCE_MINUTES

    avg = sum(clearance_values) / len(clearance_values)
    logger.info("Clearance estimate %.1f min from %d similar incidents", avg, len(clearance_values))
    return round(avg, 1)


def detect_false_positive_cluster(
    similar_incidents: list[dict],
    current_confidence: float = 1.0,
) -> bool:
    """Check if similar past incidents suggest this is a false positive.
    If majority of similar incidents had low confidence, flag as likely FP."""
    if not similar_incidents:
        return False

    low_conf_count = 0
    total = 0
    for inc in similar_incidents:
        meta = inc.get("metadata", {})
        conf = meta.get("confidence", meta.get("final_confidence"))
        if conf is not None:
            total += 1
            if conf < FALSE_POSITIVE_THRESHOLD:
                low_conf_count += 1

    if total == 0:
        return False

    fp_ratio = low_conf_count / total
    is_fp = fp_ratio > 0.6 and current_confidence < 0.6

    if is_fp:
        logger.info(
            "False positive detected: %.0f%% of %d similar had low confidence, current=%.2f",
            fp_ratio * 100, total, current_confidence,
        )
    return is_fp
