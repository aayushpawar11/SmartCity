"""
Event + incident storage. Uses aiosqlite for async operations.
Events table: legacy feed-based analysis.
Incidents table: new /process-frame pipeline with structured classification.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

EVENTS_SCHEMA = """
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

INCIDENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    confidence REAL,
    timestamp TEXT,
    lat REAL,
    lon REAL,
    rating INTEGER DEFAULT 5,
    vehicles_detected INTEGER,
    blocked_lanes INTEGER,
    clearance_minutes REAL,
    image_path TEXT,
    description TEXT,
    notification TEXT,
    raw_json TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(timestamp);
CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(event_type);
"""


def _db_path() -> str:
    return str(DB_PATH)


async def init_db() -> None:
    async with aiosqlite.connect(_db_path()) as conn:
        await conn.executescript(EVENTS_SCHEMA)
        await conn.executescript(INCIDENTS_SCHEMA)
        await conn.commit()
    logger.info("Database initialized (events + incidents tables)")


# ---------------------------------------------------------------------------
# Incidents (new pipeline)
# ---------------------------------------------------------------------------

async def save_incident(metadata: dict) -> int:
    """Insert a classified incident and return its auto-incremented id."""
    now = time.time()
    ts = metadata.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    raw = json.dumps(metadata)
    async with aiosqlite.connect(_db_path()) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO incidents
            (event_type, confidence, timestamp, lat, lon, rating,
             vehicles_detected, blocked_lanes, clearance_minutes, image_path,
             description, notification, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.get("event_type", "unknown"),
                metadata.get("confidence", 0.0),
                ts,
                metadata.get("lat", 0.0),
                metadata.get("lon", 0.0),
                metadata.get("rating", 5),
                metadata.get("vehicles_detected", 0),
                metadata.get("blocked_lanes", 0),
                metadata.get("clearance_minutes"),
                metadata.get("image_path"),
                metadata.get("description", ""),
                metadata.get("notification", ""),
                raw,
                now,
            ),
        )
        await conn.commit()
        incident_id = cursor.lastrowid
    logger.info("Saved incident %d: %s", incident_id, metadata.get("event_type"))
    return incident_id


async def update_incident_image_path(incident_id: int, image_path: str) -> None:
    async with aiosqlite.connect(_db_path()) as conn:
        await conn.execute(
            "UPDATE incidents SET image_path = ? WHERE id = ?",
            (image_path, incident_id),
        )
        await conn.commit()


async def get_recent_incidents(limit: int = 50) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT id, event_type, confidence, timestamp, lat, lon, rating,
                   vehicles_detected, blocked_lanes, clearance_minutes,
                   image_path, description, notification, created_at
            FROM incidents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [
        {
            "id": r["id"],
            "event_type": r["event_type"],
            "confidence": r["confidence"],
            "timestamp": r["timestamp"],
            "lat": r["lat"],
            "lon": r["lon"],
            "rating": r["rating"],
            "vehicles_detected": r["vehicles_detected"],
            "blocked_lanes": r["blocked_lanes"],
            "clearance_minutes": r["clearance_minutes"],
            "image_path": r["image_path"],
            "description": r["description"],
            "notification": r["notification"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Events (legacy feed-based pipeline)
# ---------------------------------------------------------------------------

async def insert_event(
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
    async with aiosqlite.connect(_db_path()) as conn:
        await conn.execute(
            """
            INSERT INTO events
            (id, feed_id, lat, lng, occurred_at, has_police, has_accident,
             hazard_level, description, image_path, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid, feed_id, lat, lng, now,
                1 if has_police else 0,
                1 if has_accident else 0,
                hazard_level, description, image_path, emb_json, now,
            ),
        )
        await conn.commit()
    return eid


async def get_events(limit: int = 200) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT id, feed_id, lat, lng, occurred_at, has_police, has_accident,
                   hazard_level, description, image_path, created_at
            FROM events
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
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


async def get_events_with_embeddings(limit: int = 500) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT id, feed_id, lat, lng, occurred_at, has_police, has_accident,
                   hazard_level, description, image_path, embedding_json, created_at
            FROM events
            WHERE embedding_json IS NOT NULL
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
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


async def get_event_by_id(eid: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM events WHERE id = ?", (eid,))
        r = await cursor.fetchone()
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
