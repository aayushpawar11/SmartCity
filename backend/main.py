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
    lat: float = Query(37.7749, description="Incident latitude"),
    lon: float = Query(-122.4194, description="Incident longitude"),
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

    logger.info("Processing frame: %.4f, %.4f (%d bytes)", lat, lon, len(image_bytes))
    result = await process_frame_pipeline(image_bytes, lat=lat, lon=lon)
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


@app.post("/seed")
async def seed():
    """Insert demo events so the map has data without running analysis."""
    await init_db()
    demos = [
        ("camera1", 37.7749, -122.4194, False, True, 8, "Red SUV collision with barrier"),
        ("camera2", 37.7849, -122.4094, True, False, 5, "Police traffic stop on Main St"),
        ("camera3", 37.7649, -122.4294, False, False, 3, "Normal traffic flow"),
        ("flood", 37.7619, -122.4244, False, False, 9, "Flooding on roadway, avoid area"),
        ("highway", 37.7689, -122.4184, False, True, 7, "Multi-vehicle accident, lane blocked"),
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
):
    """Get driving route via OSRM."""
    import httpx

    url = f"{OSRM_BASE_URL}/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"Routing failed: {e}")
    if data.get("code") != "Ok":
        raise HTTPException(404, "No route found")
    leg = data["routes"][0]["legs"][0]
    coords = data["routes"][0]["geometry"]["coordinates"]
    coordinates = [[c[1], c[0]] for c in coords]
    return {
        "coordinates": coordinates,
        "distance_meters": leg["distance"],
        "duration_seconds": leg["duration"],
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
