"""
Run analysis on feed frames and store events (with optional embeddings).
Call this periodically or via POST /analyze to simulate live updates.
"""
from __future__ import annotations

from pathlib import Path

from config import FEEDS_DIR, FRAME_INTERVAL

from analyze import analyze_frame, collect_frames_from_feeds
from embeddings import get_embedding
from store import init_db, insert_event

# Wizard of Oz: fake lat/lng per feed (use real coords if you have them)
FEED_COORDS: dict[str, tuple[float, float]] = {
    "camera1": (37.7749, -122.4194),
    "camera2": (37.7849, -122.4094),
    "camera3": (37.7649, -122.4294),
    "traffic": (37.7699, -122.4144),
    "accident": (37.7729, -122.4164),
    "police": (37.7789, -122.4124),
    "flood": (37.7619, -122.4244),
    "highway": (37.7689, -122.4184),
}


def _coords_for_feed(feed_id: str) -> tuple[float, float]:
    if feed_id in FEED_COORDS:
        return FEED_COORDS[feed_id]
    # Generate deterministic coords from feed_id
    h = hash(feed_id) % 10000
    lat = 37.77 + (h % 100) / 10000
    lng = -122.42 + (h // 100) / 10000
    return (lat, lng)


def run_once() -> list[dict]:
    """Analyze one frame per feed, store events, return new events for alerts."""
    init_db()
    frames = collect_frames_from_feeds(interval_sec=FRAME_INTERVAL)
    if not frames:
        return []
    new_events = []
    for feed_id, frame_path in frames:
        lat, lng = _coords_for_feed(feed_id)
        analysis = analyze_frame(frame_path)
        if not analysis:
            continue
        has_police = bool(analysis.get("has_police", False))
        has_accident = bool(analysis.get("has_accident", False))
        hazard_level = int(analysis.get("hazard_level", 1))
        description = str(analysis.get("description", "No description"))
        # Store path relative to backend for safe serving
        try:
            image_path = str(frame_path.relative_to(Path(__file__).parent))
        except ValueError:
            image_path = frame_path.name
        embedding = get_embedding(description)
        eid = insert_event(
            feed_id=feed_id,
            lat=lat,
            lng=lng,
            has_police=has_police,
            has_accident=has_accident,
            hazard_level=hazard_level,
            description=description,
            image_path=image_path,
            embedding=embedding,
        )
        ev = {
            "id": eid,
            "feed_id": feed_id,
            "lat": lat,
            "lng": lng,
            "has_police": has_police,
            "has_accident": has_accident,
            "hazard_level": hazard_level,
            "description": description,
            "image_path": image_path,
        }
        new_events.append(ev)
    return new_events


def run_on_single_image(image_path: Path, feed_id: str = "upload", lat: float = 37.7749, lng: float = -122.4194) -> dict | None:
    """Analyze one image and store one event. Used for demo or manual upload."""
    init_db()
    analysis = analyze_frame(image_path)
    if not analysis:
        return None
    has_police = bool(analysis.get("has_police", False))
    has_accident = bool(analysis.get("has_accident", False))
    hazard_level = int(analysis.get("hazard_level", 1))
    description = str(analysis.get("description", "No description"))
    image_path_str = str(image_path)
    embedding = get_embedding(description)
    eid = insert_event(
        feed_id=feed_id,
        lat=lat,
        lng=lng,
        has_police=has_police,
        has_accident=has_accident,
        hazard_level=hazard_level,
        description=description,
        image_path=image_path_str,
        embedding=embedding,
    )
    return {
        "id": eid,
        "feed_id": feed_id,
        "lat": lat,
        "lng": lng,
        "has_police": has_police,
        "has_accident": has_accident,
        "hazard_level": hazard_level,
        "description": description,
        "image_path": image_path_str,
    }
