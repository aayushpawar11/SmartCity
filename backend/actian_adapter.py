"""
Actian VectorAI DB adapter.
Uses AsyncCortexClient when the Docker container is reachable on ACTIAN_HOST:ACTIAN_PORT.
Falls back to an in-memory vector store so the pipeline works end-to-end without Actian.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from config import ACTIAN_HOST, ACTIAN_PORT

logger = logging.getLogger(__name__)

COLLECTION_NAME = "incidents"
VECTOR_DIM = 3072

# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------
_mem_store: dict[int, dict] = {}  # incident_id -> {"vector": [...], "metadata": {...}}

_actian_available = False
_actian_client = None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

async def init_vector_store() -> None:
    """Try connecting to Actian VectorAI with retries. Fall back to in-memory if unavailable."""
    global _actian_available, _actian_client

    if not ACTIAN_HOST:
        logger.info("ACTIAN_HOST not set, using in-memory vector store")
        return

    max_retries = 5
    for attempt in range(max_retries):
        try:
            from cortex import AsyncCortexClient, DistanceMetric

            addr = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
            client = AsyncCortexClient(addr)
            await client.__aenter__()

            version, uptime = await client.health_check()
            logger.info("Connected to Actian VectorAI: %s (uptime: %s)", version, uptime)

            if not await client.has_collection(COLLECTION_NAME):
                await client.create_collection(
                    name=COLLECTION_NAME,
                    dimension=VECTOR_DIM,
                    distance_metric=DistanceMetric.COSINE,
                )
                logger.info("Created Actian collection '%s' (dim=%d)", COLLECTION_NAME, VECTOR_DIM)
            else:
                logger.info("Actian collection '%s' already exists", COLLECTION_NAME)

            _actian_client = client
            _actian_available = True
            return

        except Exception as e:
            delay = 2 ** (attempt + 1)
            if attempt < max_retries - 1:
                logger.warning(
                    "Actian attempt %d/%d failed (%s), retrying in %ds...",
                    attempt + 1, max_retries, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    "Actian unavailable after %d attempts, using in-memory fallback",
                    max_retries,
                )
                _actian_available = False


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def upsert_vector(incident_id: int, vector: list[float], metadata: dict | None = None) -> None:
    """Store a vector keyed by incident_id. Routes to Actian or in-memory."""
    if _actian_available and _actian_client:
        try:
            await _actian_client.upsert(
                COLLECTION_NAME,
                id=incident_id,
                vector=vector,
                payload=metadata or {},
            )
            logger.debug("Actian upsert: incident %d", incident_id)
            return
        except Exception as e:
            logger.warning("Actian upsert failed (%s), falling back to memory", e)

    _mem_store[incident_id] = {"vector": vector, "metadata": metadata or {}}
    logger.debug("In-memory upsert: incident %d (total: %d)", incident_id, len(_mem_store))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

async def search_similar(vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Return top-k similar incidents. Routes to Actian or in-memory cosine search."""
    if _actian_available and _actian_client:
        try:
            results = await _actian_client.search(COLLECTION_NAME, query=vector, top_k=top_k)
            return [
                {
                    "incident_id": r.id,
                    "score": r.score,
                    "metadata": r.payload if hasattr(r, "payload") else {},
                }
                for r in results
            ]
        except Exception as e:
            logger.warning("Actian search failed (%s), falling back to memory", e)

    scored = []
    for iid, entry in _mem_store.items():
        sim = _cosine_sim(vector, entry["vector"])
        scored.append((sim, iid, entry["metadata"]))
    scored.sort(key=lambda x: -x[0])

    return [
        {"incident_id": iid, "score": sim, "metadata": meta}
        for sim, iid, meta in scored[:top_k]
    ]


# ---------------------------------------------------------------------------
# Legacy API (kept for backward compatibility with embeddings.py)
# ---------------------------------------------------------------------------

def insert_embedding_actian(event_id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
    """Sync wrapper for legacy code paths."""
    _mem_store[hash(event_id) % 2**31] = {"vector": embedding, "metadata": metadata}


def search_actian(query_embedding: list[float], top_k: int = 20) -> list[dict[str, Any]]:
    """Sync search for legacy code paths."""
    scored = []
    for iid, entry in _mem_store.items():
        sim = _cosine_sim(query_embedding, entry["vector"])
        scored.append((sim, iid, entry["metadata"]))
    scored.sort(key=lambda x: -x[0])
    return [entry["metadata"] for _, _, entry in scored[:top_k]]
