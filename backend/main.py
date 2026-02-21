"""
SmartCity Hackathon API: events for map, vector search, and analysis trigger.
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import FEEDS_DIR
from embeddings import get_embedding
from pipeline import run_once, run_on_single_image
from search import search_events
from store import get_events, get_event_by_id, init_db, insert_event

app = FastAPI(title="SmartCity Safety API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/events")
def events(limit: int = Query(200, le=500)):
    """List recent events for the map. Poll every 5s for real-time feel."""
    return get_events(limit=limit)


@app.get("/events/{event_id}")
def event_detail(event_id: str):
    """Single event (screenshot path + description) for pin popup."""
    ev = get_event_by_id(event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    return ev


@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Semantic search: 'accidents involving trucks' -> events with vector similarity."""
    results = search_events(q, top_k=20)
    return {"query": q, "results": results}


@app.post("/analyze")
def analyze():
    """Wizard of Oz: run frame capture + Gemini on feeds dir, store events. Returns new events for TTS alerts."""
    new_events = run_once()
    return {"new_events": new_events, "count": len(new_events)}


@app.post("/seed")
def seed():
    """Insert demo events so the map has data without running analysis (no feeds needed)."""
    init_db()
    demos = [
        ("camera1", 37.7749, -122.4194, False, True, 8, "Red SUV collision with barrier"),
        ("camera2", 37.7849, -122.4094, True, False, 5, "Police traffic stop on Main St"),
        ("camera3", 37.7649, -122.4294, False, False, 3, "Normal traffic flow"),
        ("flood", 37.7619, -122.4244, False, False, 9, "Flooding on roadway, avoid area"),
        ("highway", 37.7689, -122.4184, False, True, 7, "Multi-vehicle accident, lane blocked"),
    ]
    for feed_id, lat, lng, has_police, has_accident, hazard_level, description in demos:
        emb = get_embedding(description)  # optional: enables vector search
        insert_event(
            feed_id=feed_id,
            lat=lat,
            lng=lng,
            has_police=has_police,
            has_accident=has_accident,
            hazard_level=hazard_level,
            description=description,
            image_path=None,
            embedding=emb,
        )
    return {"message": "Seeded 5 demo events", "events": get_events(limit=5)}


OSRM_BASE = "https://router.project-osrm.org"


@app.get("/route")
def route(
    from_lat: float = Query(..., description="Origin latitude"),
    from_lng: float = Query(..., description="Origin longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lng: float = Query(..., description="Destination longitude"),
):
    """Get driving route (OSRM, free). Returns GeoJSON coordinates and distance/duration."""
    import httpx

    url = f"{OSRM_BASE}/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"Routing failed: {e}")
    if data.get("code") != "Ok":
        raise HTTPException(404, "No route found")
    leg = data["routes"][0]["legs"][0]
    coords = data["routes"][0]["geometry"]["coordinates"]
    # OSRM returns [lng, lat]; we use [lat, lng] in frontend
    coordinates = [[c[1], c[0]] for c in coords]
    return {
        "coordinates": coordinates,
        "distance_meters": leg["distance"],
        "duration_seconds": leg["duration"],
    }


@app.get("/image")
def serve_image(path: str = Query(..., description="Relative path to image from backend root")):
    """Serve frame image for map popup. path is relative to backend (e.g. feeds/camera1_frame_0.jpg)."""
    # Prevent path traversal
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
