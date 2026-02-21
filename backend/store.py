"""
Event + vector storage. Uses SQLite + in-memory vectors by default.
Swap to Actian VectorAI when ACTIAN_CONNECTION_STRING is set (see actian_adapter.py).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from config import ACTIAN_ENABLED, DB_PATH

# Ensure data dir exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    feed_id TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    occurred_at REAL NOT NULL,
    has_police INTEGER NOT NULL,
    has_accident INTEGER NOT NULL,
    hazard_level INTEGER NOT NULL,
    description TEXT NOT NULL,
    image_path TEXT,
    embedding_json TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_hazard ON events(hazard_level);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as c:
        c.executescript(SCHEMA)


def insert_event(
    feed_id: str,
    lat: float,
    lng: float,
    has_police: bool,
    has_accident: bool,
    hazard_level: int,
    description: str,
    image_path: str | None = None,
    embedding: list[float] | None = None,
) -> str:
    eid = str(uuid.uuid4())
    now = time.time()
    emb_json = json.dumps(embedding) if embedding else None
    with _get_conn() as c:
        c.execute(
            """
            INSERT INTO events
            (id, feed_id, lat, lng, occurred_at, has_police, has_accident, hazard_level, description, image_path, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                feed_id,
                lat,
                lng,
                now,
                1 if has_police else 0,
                1 if has_accident else 0,
                hazard_level,
                description,
                image_path,
                emb_json,
                now,
            ),
        )
    return eid


def get_events(limit: int = 200) -> list[dict[str, Any]]:
    with _get_conn() as c:
        rows = c.execute(
            """
            SELECT id, feed_id, lat, lng, occurred_at, has_police, has_accident,
                   hazard_level, description, image_path, created_at
            FROM events
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "feed_id": r["feed_id"],
            "lat": r["lat"],
            "lng": r["lng"],
            "occurred_at": r["occurred_at"],
            "has_police": bool(r["has_police"]),
            "has_accident": bool(r["has_accident"]),
            "hazard_level": int(r["hazard_level"]),
            "description": r["description"],
            "image_path": r["image_path"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_events_with_embeddings(limit: int = 500) -> list[dict[str, Any]]:
    """For vector search when not using Actian: load all and filter in memory."""
    with _get_conn() as c:
        rows = c.execute(
            """
            SELECT id, feed_id, lat, lng, occurred_at, has_police, has_accident,
                   hazard_level, description, image_path, embedding_json, created_at
            FROM events
            WHERE embedding_json IS NOT NULL
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        emb = json.loads(r["embedding_json"]) if r["embedding_json"] else None
        out.append(
            {
                "id": r["id"],
                "feed_id": r["feed_id"],
                "lat": r["lat"],
                "lng": r["lng"],
                "occurred_at": r["occurred_at"],
                "has_police": bool(r["has_police"]),
                "has_accident": bool(r["has_accident"]),
                "hazard_level": int(r["hazard_level"]),
                "description": r["description"],
                "image_path": r["image_path"],
                "embedding": emb,
                "created_at": r["created_at"],
            }
        )
    return out


def get_event_by_id(eid: str) -> dict[str, Any] | None:
    with _get_conn() as c:
        r = c.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    if not r:
        return None
    return {
        "id": r["id"],
        "feed_id": r["feed_id"],
        "lat": r["lat"],
        "lng": r["lng"],
        "occurred_at": r["occurred_at"],
        "has_police": bool(r["has_police"]),
        "has_accident": bool(r["has_accident"]),
        "hazard_level": int(r["hazard_level"]),
        "description": r["description"],
        "image_path": r["image_path"],
        "created_at": r["created_at"],
    }
