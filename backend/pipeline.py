"""
Pipeline orchestration:
  - process_frame_pipeline(): new full pipeline (Gemini → SQL → Actian → Sphinx → OSRM)
  - get_route(): async OSRM routing with alternative support
  - run_once() / run_on_single_image(): legacy feed-based analysis (kept for /analyze)
"""
from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

_thread_pool = ThreadPoolExecutor(max_workers=4)


async def _run_in_thread(func, *args):
    """Python 3.8-compatible replacement for asyncio.to_thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_thread_pool, functools.partial(func, *args))

from config import FEEDS_DIR, FRAME_INTERVAL, OSRM_BASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# New: Full process-frame pipeline
# ---------------------------------------------------------------------------


async def process_frame_pipeline(
    image_bytes: bytes,
    lat: float = 33.749,
    lon: float = -84.388,
    filename_hint: str = "",
) -> dict[str, Any]:
    """Full orchestration: image → classify → store → embed → vector search → reason → route."""
    from analyze import analyze_frame_with_gemini, run_sphinx_decision_engine
    from embeddings import build_incident_text, generate_embedding
    from store import save_incident, update_incident_image_path
    from actian_adapter import upsert_vector, search_similar, _actian_available
    from search import estimate_clearance, detect_false_positive_cluster

    # 1) Classify the image (Gemini, with filename-based fallback)
    logger.info("Step 1: Gemini classification")
    incident = await analyze_frame_with_gemini(image_bytes, filename_hint=filename_hint)
    incident["lat"] = lat
    incident["lon"] = lon

    # 2) Save frame to disk
    frames_dir = Path(__file__).parent / "frames"
    frames_dir.mkdir(exist_ok=True)
    # We save with a temp name first, then rename after we get the incident ID
    import time as _time
    temp_name = f"frame_{int(_time.time() * 1000)}.jpg"
    temp_path = frames_dir / temp_name
    temp_path.write_bytes(image_bytes)

    # 3) SQL: store incident metadata
    logger.info("Step 2: Save incident to SQL")
    notification = _build_notification(incident)
    incident["notification"] = notification
    incident["image_path"] = f"frames/{temp_name}"
    incident_id = await save_incident(incident)
    incident["id"] = incident_id

    # Rename frame file to incident ID and update DB
    final_name = f"frame_{incident_id}.jpg"
    final_path = frames_dir / final_name
    temp_path.rename(final_path)
    incident["image_path"] = f"frames/{final_name}"
    await update_incident_image_path(incident_id, incident["image_path"])

    # 4) Embedding: generate vector from incident text
    logger.info("Step 3: Generate embedding")
    text = build_incident_text(incident)
    vector = generate_embedding(text)

    # 5) Actian (or in-memory fallback): upsert vector
    logger.info("Step 4: Upsert vector")
    await upsert_vector(incident_id, vector, metadata={
        "event_type": incident.get("event_type"),
        "confidence": incident.get("confidence"),
        "rating": incident.get("rating"),
        "clearance_minutes": incident.get("clearance_minutes"),
    })

    # 6) Vector search: find similar past incidents
    logger.info("Step 5: Search similar incidents")
    similar = await search_similar(vector, top_k=5)

    # 7) Aggregation: estimate clearance + false positive check
    logger.info("Step 6: Clearance estimate + FP detection")
    clearance = estimate_clearance(similar)
    is_fp = detect_false_positive_cluster(similar, incident.get("confidence", 0.5))

    # 8) Sphinx: AI reasoning over aggregated data
    logger.info("Step 7: Sphinx decision engine")
    sphinx_payload = {
        **incident,
        "similar_count": len(similar),
        "estimated_clearance": clearance,
        "is_false_positive": is_fp,
    }
    decision = await _run_in_thread(run_sphinx_decision_engine, sphinx_payload)

    # 9) OSRM: route adjustment if rerouting is recommended
    route_data = None
    if decision.get("action") == "reroute" and incident.get("blocked_lanes", 0) > 0:
        logger.info("Step 8: OSRM reroute")
        route_data = await get_route(
            start_lat=lat, start_lon=lon,
            end_lat=lat + 0.01, end_lon=lon + 0.01,
            alternatives=True,
        )
    else:
        logger.info("Step 8: No reroute needed")

    # 10) Assemble response matching demo schema
    response = {
        "incident": {
            "id": incident_id,
            "event_type": incident.get("event_type", "unknown"),
            "confidence": incident.get("confidence", 0.0),
            "rating": incident.get("rating", 5),
            "vehicles_detected": incident.get("vehicles_detected", 0),
            "blocked_lanes": incident.get("blocked_lanes", 0),
            "description": incident.get("description", ""),
            "lat": lat,
            "lon": lon,
            "image_path": incident.get("image_path"),
            "timestamp": incident.get("timestamp", ""),
        },
        "similar_incidents": [
            {
                "id": s.get("incident_id"),
                "event_type": s.get("metadata", {}).get("event_type", "unknown"),
                "confidence": s.get("metadata", {}).get("confidence", 0.0),
                "score": s.get("score", 0.0),
            }
            for s in similar
        ],
        "estimated_clearance_minutes": clearance,
        "notification": notification,
        "decision": decision,
        "route": route_data,
        "debug": {
            "analysis_provider": "gemini_placeholder_for_yolov8",
            "vector_store": "actian" if _actian_available else "memory",
        },
    }
    logger.info("Pipeline complete: %s → %s", incident.get("event_type"), decision.get("action"))
    return response


def _build_notification(incident: dict) -> str:
    """Generate a user-facing notification string from incident data."""
    etype = incident.get("event_type", "unknown")
    rating = incident.get("rating", 5)
    labels = {
        "accident": "Accident reported",
        "speed_sensor": "Speed sensor detected",
        "hazard": "Road hazard detected",
    }
    base = labels.get(etype, "Incident detected")
    if rating >= 7:
        return f"{base} ahead — severity {rating}/10. Consider alternate route."
    return f"{base} ahead near your route."


# ---------------------------------------------------------------------------
# OSRM routing
# ---------------------------------------------------------------------------


async def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    alternatives: bool = False,
) -> dict[str, Any] | None:
    """Call OSRM for a driving route. Optionally request alternatives."""
    url = f"{OSRM_BASE_URL}/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": "true" if alternatives else "false",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.error("OSRM routing failed: %s", e)
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    leg = route["legs"][0]
    coords = route["geometry"]["coordinates"]
    coordinates = [[c[1], c[0]] for c in coords]

    result: dict[str, Any] = {
        "coordinates": coordinates,
        "distance_meters": leg["distance"],
        "duration_seconds": leg["duration"],
    }

    if alternatives and len(data["routes"]) > 1:
        alt = data["routes"][1]
        alt_leg = alt["legs"][0]
        alt_coords = [[c[1], c[0]] for c in alt["geometry"]["coordinates"]]
        result["alternative"] = {
            "coordinates": alt_coords,
            "distance_meters": alt_leg["distance"],
            "duration_seconds": alt_leg["duration"],
        }

    return result


# ---------------------------------------------------------------------------
# Legacy: feed-based pipeline (kept for /analyze and /seed)
# ---------------------------------------------------------------------------

from analyze import analyze_frame, collect_frames_from_feeds
from embeddings import get_embedding
from store import init_db, insert_event

FEED_COORDS: dict[str, tuple[float, float]] = {
    "camera1": (33.749, -84.388),
    "camera2": (33.760, -84.375),
    "camera3": (33.740, -84.400),
    "traffic": (33.755, -84.390),
    "accident": (33.880, -84.272),
    "police": (33.770, -84.365),
    "flood": (33.735, -84.410),
    "highway": (33.790, -84.350),
}


def _coords_for_feed(feed_id: str) -> tuple[float, float]:
    if feed_id in FEED_COORDS:
        return FEED_COORDS[feed_id]
    h = hash(feed_id) % 10000
    lat = 33.75 + (h % 100) / 10000
    lng = -84.39 + (h // 100) / 10000
    return (lat, lng)


async def run_once() -> list[dict]:
    """Analyze one frame per feed, store events, return new events for alerts."""
    await init_db()
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
        try:
            image_path = str(frame_path.relative_to(Path(__file__).parent))
        except ValueError:
            image_path = frame_path.name
        embedding = get_embedding(description)
        eid = await insert_event(
            feed_id=feed_id, lat=lat, lng=lng,
            has_police=has_police, has_accident=has_accident,
            hazard_level=hazard_level, description=description,
            image_path=image_path, embedding=embedding,
        )
        new_events.append({
            "id": eid, "feed_id": feed_id, "lat": lat, "lng": lng,
            "has_police": has_police, "has_accident": has_accident,
            "hazard_level": hazard_level, "description": description,
            "image_path": image_path,
        })
    return new_events


async def run_on_single_image(
    image_path: Path,
    feed_id: str = "upload",
    lat: float = 33.749,
    lng: float = -84.388,
) -> dict | None:
    await init_db()
    analysis = analyze_frame(image_path)
    if not analysis:
        return None
    has_police = bool(analysis.get("has_police", False))
    has_accident = bool(analysis.get("has_accident", False))
    hazard_level = int(analysis.get("hazard_level", 1))
    description = str(analysis.get("description", "No description"))
    image_path_str = str(image_path)
    embedding = get_embedding(description)
    eid = await insert_event(
        feed_id=feed_id, lat=lat, lng=lng,
        has_police=has_police, has_accident=has_accident,
        hazard_level=hazard_level, description=description,
        image_path=image_path_str, embedding=embedding,
    )
    return {
        "id": eid, "feed_id": feed_id, "lat": lat, "lng": lng,
        "has_police": has_police, "has_accident": has_accident,
        "hazard_level": hazard_level, "description": description,
        "image_path": image_path_str,
    }
