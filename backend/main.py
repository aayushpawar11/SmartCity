"""
SmartCity Traffic Intelligence API.
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

app = FastAPI(title="SmartCity Traffic Intelligence API", version="0.2.0")
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
    avoid_lat: float = Query(None, description="Incident latitude to avoid"),
    avoid_lng: float = Query(None, description="Incident longitude to avoid"),
):
    """Get driving route via OSRM. When avoid_lat/avoid_lng are set, returns an alternative route."""
    import httpx
    import math

    waypoints = f"{from_lng},{from_lat};{to_lng},{to_lat}"
    params = {"overview": "full", "geometries": "geojson", "alternatives": "true"}

    if avoid_lat is not None and avoid_lng is not None:
        bearing = math.atan2(to_lng - from_lng, to_lat - from_lat)
        perp = bearing + math.pi / 2
        offset = 0.02
        via_lat = avoid_lat + offset * math.cos(perp)
        via_lng = avoid_lng + offset * math.sin(perp)
        waypoints = f"{from_lng},{from_lat};{via_lng},{via_lat};{to_lng},{to_lat}"

    url = f"{OSRM_BASE_URL}/route/v1/driving/{waypoints}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"Routing failed: {e}")
    if data.get("code") != "Ok" or not data.get("routes"):
        raise HTTPException(404, "No route found")

    chosen = data["routes"][0]

    if avoid_lat is not None and avoid_lng is not None and len(data["routes"]) > 1:
        best_dist = 0
        for rt in data["routes"]:
            route_coords = rt["geometry"]["coordinates"]
            min_d = min(
                math.sqrt((c[1] - avoid_lat) ** 2 + (c[0] - avoid_lng) ** 2)
                for c in route_coords
            )
            if min_d > best_dist:
                best_dist = min_d
                chosen = rt

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
