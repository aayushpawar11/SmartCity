"""
LookOut — Traffic Intelligence API.
All endpoints are async. The /process-frame endpoint runs the full pipeline:
  Gemini → SQL → Embedding → Actian → Similarity → Sphinx → OSRM → Response
"""
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from actian_adapter import init_vector_store
from config import OSRM_BASE_URL
from embeddings import get_embedding
from pipeline import process_frame_pipeline, run_once, run_on_single_image
from search import search_events
from store import get_events, get_event_by_id, get_recent_incidents, init_db, insert_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LookOut — Traffic Intelligence API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    await init_vector_store()
    logger.info("Backend ready")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Lightweight liveness check."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# New pipeline: /process-frame
# ---------------------------------------------------------------------------

@app.post("/process-frame")
async def process_frame(
    file: UploadFile = File(...),
    lat: float = Query(33.749, description="Incident latitude"),
    lon: float = Query(-84.388, description="Incident longitude"),
):
    """Full pipeline: image → Gemini classify → SQL → Actian vector → Sphinx reason → OSRM route.

    Upload a traffic camera frame and receive:
    - Incident classification
    - Similar past incidents
    - Estimated clearance time
    - AI decision (reroute / monitor / dismiss)
    - Optional alternative route
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Empty file")

    fname = file.filename or ""
    logger.info("Processing frame: %.4f, %.4f (%d bytes, %s)", lat, lon, len(image_bytes), fname)
    result = await process_frame_pipeline(image_bytes, lat=lat, lon=lon, filename_hint=fname)
    return result


# ---------------------------------------------------------------------------
# Incidents (new pipeline data)
# ---------------------------------------------------------------------------

@app.get("/incidents")
async def list_incidents(limit: int = Query(50, le=200)):
    """List recent classified incidents from the /process-frame pipeline."""
    return await get_recent_incidents(limit=limit)


# ---------------------------------------------------------------------------
# Legacy endpoints (all converted to async)
# ---------------------------------------------------------------------------

@app.get("/events")
async def events(limit: int = Query(200, le=500)):
    """List recent events for the map."""
    return await get_events(limit=limit)


@app.get("/events/{event_id}")
async def event_detail(event_id: str):
    """Single event for pin popup."""
    ev = await get_event_by_id(event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    return ev


@app.get("/search")
async def search(q: str = Query(..., min_length=1)):
    """Semantic search over events."""
    results = await search_events(q, top_k=20)
    return {"query": q, "results": results}


@app.post("/analyze")
async def analyze():
    """Run frame capture + Gemini on feeds dir, store events."""
    new_events = await run_once()
    return {"new_events": new_events, "count": len(new_events)}


@app.post("/seed-feeds")
async def seed_feeds():
    """Process every image in backend/feeds through the full pipeline.

    Filename convention: lat_lon_type.jpg  (e.g. 33.880244_-84.271938_accident.jpg)
    Each image goes through: Gemini → SQL → Embedding → Actian → Sphinx → OSRM
    """
    feeds_dir = Path(__file__).parent / "feeds"
    if not feeds_dir.exists():
        raise HTTPException(404, "feeds/ directory not found")

    images = sorted(
        p for p in feeds_dir.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and p.is_file()
    )
    if not images:
        return {"message": "No images found in feeds/", "results": []}

    results = []
    for img_path in images:
        parts = img_path.stem.split("_")
        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except (IndexError, ValueError):
            logger.warning("Skipping %s — can't parse lat_lon from filename", img_path.name)
            continue

        image_bytes = img_path.read_bytes()
        logger.info("seed-feeds: processing %s (%.4f, %.4f, %d bytes)", img_path.name, lat, lon, len(image_bytes))
        result = await process_frame_pipeline(image_bytes, lat=lat, lon=lon, filename_hint=img_path.stem)
        results.append({
            "file": img_path.name,
            "incident_id": result["incident"]["id"],
            "event_type": result["incident"]["event_type"],
            "rating": result["incident"]["rating"],
            "decision": result["decision"]["action"],
        })

    return {"message": f"Processed {len(results)} feed images", "results": results}


@app.post("/seed")
async def seed():
    """Insert demo events so the map has data without running analysis."""
    await init_db()
    demos = [
        ("camera1", 33.749, -84.388, False, True, 8, "Red SUV collision with barrier"),
        ("camera2", 33.760, -84.375, True, False, 5, "Police traffic stop on Peachtree St"),
        ("camera3", 33.740, -84.400, False, False, 3, "Normal traffic flow"),
        ("flood", 33.735, -84.410, False, False, 9, "Flooding on roadway, avoid area"),
        ("highway", 33.790, -84.350, False, True, 7, "Multi-vehicle accident on I-85, lane blocked"),
    ]
    for feed_id, lat, lng, has_police, has_accident, hazard_level, description in demos:
        emb = get_embedding(description)
        await insert_event(
            feed_id=feed_id, lat=lat, lng=lng,
            has_police=has_police, has_accident=has_accident,
            hazard_level=hazard_level, description=description,
            image_path=None, embedding=emb,
        )
    evts = await get_events(limit=5)
    return {"message": "Seeded 5 demo events", "events": evts}


@app.get("/route")
async def route(
    from_lat: float = Query(..., description="Origin latitude"),
    from_lng: float = Query(..., description="Origin longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lng: float = Query(..., description="Destination longitude"),
    avoid: str = Query(None, description="Semicolon-separated lat,lng pairs to avoid"),
):
    """Get driving route via OSRM, avoiding incident locations."""
    import httpx
    import math
    import asyncio

    avoid_points: list[tuple[float, float]] = []
    if avoid:
        for pair in avoid.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            parts = pair.split(",")
            if len(parts) == 2:
                try:
                    avoid_points.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

    params = {"overview": "full", "geometries": "geojson", "alternatives": "true"}

    async def fetch_routes(client: httpx.AsyncClient, wp: str) -> list:
        url = f"{OSRM_BASE_URL}/route/v1/driving/{wp}"
        try:
            r = await client.get(url, params=params)
            if r.status_code == 429:
                await asyncio.sleep(1.5)
                r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            if data.get("code") == "Ok" and data.get("routes"):
                return data["routes"]
        except Exception:
            pass
        return []

    async with httpx.AsyncClient(timeout=20.0) as client:
        if not avoid_points:
            wp = f"{from_lng},{from_lat};{to_lng},{to_lat}"
            candidates = await fetch_routes(client, wp)
            if not candidates:
                raise HTTPException(404, "No route found")
            chosen = candidates[0]
        else:
            # Get the direct (shortest) route duration as a baseline
            direct_wp = f"{from_lng},{from_lat};{to_lng},{to_lat}"
            direct_routes = await fetch_routes(client, direct_wp)
            base_duration = float("inf")
            if direct_routes:
                base_duration = sum(
                    leg["duration"] for leg in direct_routes[0]["legs"]
                )

            # 0.003 degrees ≈ 330m — if a route passes closer than this
            # to an incident we consider it "hitting" the incident
            INCIDENT_RADIUS = 0.003

            def score_route(rt: dict) -> float:
                """Balance incident avoidance with route efficiency.
                Penalise routes that are much longer than the direct route."""
                route_coords = rt["geometry"]["coordinates"]
                duration = sum(leg["duration"] for leg in rt["legs"])

                # How far does this route stay from each incident?
                min_clearance = float("inf")
                for alat, alng in avoid_points:
                    closest = min(
                        math.sqrt((c[1] - alat) ** 2 + (c[0] - alng) ** 2)
                        for c in route_coords
                    )
                    min_clearance = min(min_clearance, closest)

                # Does the route actually clear all incidents?
                clears = min_clearance > INCIDENT_RADIUS

                # Duration penalty: ratio of this route to the direct route.
                # A route 1.5x longer than direct gets a big penalty.
                dur_ratio = duration / base_duration if base_duration > 0 else 1.0

                if clears:
                    # Good route: reward clearance, penalise excessive length
                    return 1000 + min_clearance - dur_ratio * 0.5
                else:
                    # Still hits an incident: prefer the one that at least
                    # has some clearance, but don't reward long detours
                    return min_clearance - dur_ratio * 0.5

            # Vector math for perpendicular offset direction
            dx = to_lat - from_lat
            dy = to_lng - from_lng
            route_len = math.sqrt(dx * dx + dy * dy) or 1e-9
            px, py = -dy / route_len, dx / route_len

            centroid_lat = sum(p[0] for p in avoid_points) / len(avoid_points)
            centroid_lng = sum(p[1] for p in avoid_points) / len(avoid_points)
            cx = centroid_lat - from_lat
            cy = centroid_lng - from_lng
            perp_dot = cx * px + cy * py
            prefer_sign = -1 if perp_dot >= 0 else 1

            mid_lat = (from_lat + to_lat) / 2
            mid_lng = (from_lng + to_lng) / 2

            # Moderate offsets: 0.04° ≈ 4.5km, 0.08° ≈ 9km, 0.13° ≈ 14km
            waypoint_sets = []
            for off in [0.04, 0.08, 0.13]:
                s = prefer_sign
                via_lat = mid_lat + s * off * px
                via_lng = mid_lng + s * off * py
                waypoint_sets.append(
                    f"{from_lng},{from_lat};{via_lng},{via_lat};{to_lng},{to_lat}"
                )
            # Other side at a small offset
            via_lat = mid_lat - prefer_sign * 0.06 * px
            via_lng = mid_lng - prefer_sign * 0.06 * py
            waypoint_sets.append(
                f"{from_lng},{from_lat};{via_lng},{via_lat};{to_lng},{to_lat}"
            )

            all_candidates = list(direct_routes) if direct_routes else []
            for wp in waypoint_sets:
                routes = await fetch_routes(client, wp)
                all_candidates.extend(routes)
                await asyncio.sleep(1.1)

            if not all_candidates:
                raise HTTPException(404, "No route found")

            chosen = max(all_candidates, key=score_route)

    coords = chosen["geometry"]["coordinates"]
    coordinates = [[c[1], c[0]] for c in coords]
    total_distance = sum(leg["distance"] for leg in chosen["legs"])
    total_duration = sum(leg["duration"] for leg in chosen["legs"])
    return {
        "coordinates": coordinates,
        "distance_meters": total_distance,
        "duration_seconds": total_duration,
    }


@app.get("/image")
async def serve_image(path: str = Query(..., description="Relative path to image")):
    """Serve frame image for map popup."""
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    base = Path(__file__).parent
    candidate = (base / path).resolve()
    if not str(candidate).startswith(str(base.resolve())) or not candidate.exists() or not candidate.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(candidate)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
