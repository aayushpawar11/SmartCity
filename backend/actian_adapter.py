"""
Actian VectorAI DB adapter for the "Best Use of Actian VectorAI DB" track.
When ACTIAN_CONNECTION_STRING is set, use this to store/query embeddings.
Otherwise the app uses SQLite + in-memory vector search (see store.py + search.py).
"""
from __future__ import annotations

from typing import Any

# TODO: When hackathon provides Actian VectorAI SDK or REST API, implement:
# - connect(connection_string)
# - insert_embedding(id, vector, metadata)
# - search_similar(vector, top_k) -> list of (id, score, metadata)
# Then in store.py and search.py, branch on ACTIAN_ENABLED and call this adapter.

def insert_embedding_actian(event_id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
    """Store event embedding in Actian VectorAI. Replace with real client when available."""
    raise NotImplementedError(
        "Actian VectorAI: set ACTIAN_CONNECTION_STRING and implement using hackathon-provided SDK/Docker."
    )


def search_actian(query_embedding: list[float], top_k: int = 20) -> list[dict[str, Any]]:
    """Semantic search in Actian. Replace with real client when available."""
    raise NotImplementedError(
        "Actian VectorAI: set ACTIAN_CONNECTION_STRING and implement using hackathon-provided SDK/Docker."
    )
