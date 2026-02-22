"""
Analysis layer:
  - analyze_frame(): legacy feed-based Gemini Vision (unchanged)
  - analyze_frame_with_gemini(): new structured incident classifier
  - run_sphinx_decision_engine(): Sphinx CLI reasoning over incident data
Uses Gemini REST API directly (no SDK needed — works on any Python version).
"""
from __future__ import annotations

import base64
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from config import FEEDS_DIR, GEMINI_API_KEY, SPHINX_ENABLED

GEMINI_BASE = "https://generativelanguage.googleapis.com"
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# New: Structured incident classification from raw image bytes
# ---------------------------------------------------------------------------

INCIDENT_PROMPT = """You are a traffic incident classifier analyzing a camera frame.
Classify what you see into exactly one of three categories. Return ONLY valid JSON, no markdown:
{
  "event_type": "one of: accident, speed_sensor, hazard",
  "confidence": 0.0 to 1.0,
  "vehicles_detected": integer count of vehicles visible,
  "blocked_lanes": integer count of lanes blocked (0 if none),
  "rating": integer from 1 to 10 indicating severity (1 = minor, 10 = catastrophic),
  "description": "One sentence describing the scene"
}

Category guidance:
- accident: any collision, crash, vehicle damage, overturned vehicle, or multi-vehicle incident
- speed_sensor: speed monitoring devices, radar traps, speed cameras, or speed-related enforcement
- hazard: any road danger that is NOT a collision — debris, flooding, fire, construction, stalled vehicle, poor visibility, potholes, fallen trees, etc."""


async def _call_gemini(payload: dict) -> dict | None:
    """Try multiple Gemini model names and API versions until one succeeds."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in GEMINI_MODELS:
            for version in ("v1beta", "v1"):
                url = f"{GEMINI_BASE}/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        logger.info("Gemini OK via %s/%s", version, model)
                        return resp.json()
                    logger.warning("Gemini %s/%s returned %d: %s", version, model, resp.status_code, resp.text[:200])
                except Exception as e:
                    logger.warning("Gemini %s/%s error: %s", version, model, e)
    return None


async def analyze_frame_with_gemini(image_bytes: bytes, filename_hint: str = "") -> dict:
    """Send image bytes to Gemini Flash via REST API, return structured incident JSON."""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY, using filename fallback")
        return _incident_fallback(filename_hint)

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}},
                {"text": INCIDENT_PROMPT},
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }
    try:
        data = await _call_gemini(payload)
        if not data:
            logger.error("All Gemini models failed, using filename fallback")
            return _incident_fallback(filename_hint)

        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(text)
        logger.info("Gemini classified: %s (%.2f)", result.get("event_type"), result.get("confidence", 0))
        return result
    except Exception as e:
        logger.error("Gemini analysis failed: %s", e)
        return _incident_fallback(filename_hint)


def _incident_fallback(filename_hint: str = "") -> dict:
    """Smart fallback that infers classification from the filename when Gemini is down."""
    hint = filename_hint.lower()
    if any(w in hint for w in ("accident", "crash", "collision")):
        return {
            "event_type": "accident",
            "confidence": 0.85,
            "vehicles_detected": 2,
            "blocked_lanes": 1,
            "rating": 8,
            "description": "Vehicle accident detected (classified from feed metadata)",
        }
    if any(w in hint for w in ("speed", "radar", "sensor", "trap", "camera")):
        return {
            "event_type": "speed_sensor",
            "confidence": 0.80,
            "vehicles_detected": 0,
            "blocked_lanes": 0,
            "rating": 4,
            "description": "Speed monitoring device detected (classified from feed metadata)",
        }
    if any(w in hint for w in ("hazard", "obstacle", "debris", "flood", "fire", "construction")):
        return {
            "event_type": "hazard",
            "confidence": 0.75,
            "vehicles_detected": 0,
            "blocked_lanes": 1,
            "rating": 6,
            "description": "Road hazard detected (classified from feed metadata)",
        }
    return {
        "event_type": "hazard",
        "confidence": 0.5,
        "vehicles_detected": 0,
        "blocked_lanes": 0,
        "rating": 5,
        "description": "Incident detected — awaiting classification",
    }


# ---------------------------------------------------------------------------
# Sphinx CLI decision engine
# ---------------------------------------------------------------------------

SPHINX_OUTPUT_SCHEMA = json.dumps({
    "action": {"type": "string"},
    "final_confidence": {"type": "number"},
    "explanation": {"type": "string"},
})


def run_sphinx_decision_engine(payload: dict) -> dict:
    """Call sphinx-cli with incident data and get a structured decision back."""
    if not SPHINX_ENABLED:
        logger.info("Sphinx disabled, returning default decision")
        return _sphinx_fallback(payload)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="sphinx_"
        ) as f:
            json.dump(payload, f)
            tmp_path = f.name

        prompt = (
            f"You are a traffic operations decision engine. "
            f"Given this incident data from file {tmp_path}: "
            f"Event type: {payload.get('event_type', 'unknown')}, "
            f"Confidence: {payload.get('confidence', 0)}, "
            f"Rating: {payload.get('rating', 5)}/10, "
            f"Vehicles: {payload.get('vehicles_detected', 0)}, "
            f"Blocked lanes: {payload.get('blocked_lanes', 0)}, "
            f"Similar incidents found: {payload.get('similar_count', 0)}, "
            f"Estimated clearance: {payload.get('estimated_clearance', 'unknown')} min, "
            f"Is false positive: {payload.get('is_false_positive', False)}. "
            f"Decide: should we reroute traffic, monitor, dispatch, or dismiss? "
            f"Return your decision as structured JSON."
        )

        result = subprocess.run(
            [
                "sphinx-cli", "chat",
                "--prompt", prompt,
                "--output-schema", SPHINX_OUTPUT_SCHEMA,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            logger.warning("Sphinx CLI failed (exit %d): %s", result.returncode, result.stderr[:200])
            return _sphinx_fallback(payload)

        output = result.stdout.strip()
        if output.startswith("```"):
            output = output.split("\n", 1)[-1].rsplit("```", 1)[0]

        decision = json.loads(output)
        logger.info("Sphinx decision: %s (%.2f)", decision.get("action"), decision.get("final_confidence", 0))
        return decision

    except json.JSONDecodeError as e:
        logger.warning("Sphinx returned invalid JSON: %s", e)
        return _sphinx_fallback(payload)
    except subprocess.TimeoutExpired:
        logger.warning("Sphinx CLI timed out")
        return _sphinx_fallback(payload)
    except FileNotFoundError:
        logger.warning("sphinx-cli not found on PATH")
        return _sphinx_fallback(payload)
    except Exception as e:
        logger.error("Sphinx error: %s", e)
        return _sphinx_fallback(payload)


def _sphinx_fallback(payload: dict) -> dict:
    """Deterministic fallback when Sphinx is unavailable."""
    confidence = payload.get("confidence", 0.5)
    rating = payload.get("rating", 5)

    if payload.get("is_false_positive"):
        return {"action": "dismiss", "final_confidence": confidence * 0.3, "explanation": "Likely false positive based on similar incidents"}

    if rating >= 7 and confidence > 0.7:
        return {"action": "reroute", "final_confidence": confidence, "explanation": f"High severity (rating {rating}/10) {payload.get('event_type', 'incident')} with strong confidence"}

    if rating >= 4 or confidence > 0.5:
        return {"action": "monitor", "final_confidence": confidence, "explanation": f"Moderate incident (rating {rating}/10) — monitoring recommended"}

    return {"action": "monitor", "final_confidence": confidence, "explanation": f"Low severity (rating {rating}/10) — continue monitoring"}


# ---------------------------------------------------------------------------
# Legacy: feed-based frame analysis (kept for /analyze endpoint)
# ---------------------------------------------------------------------------

PROMPT = """Analyze this traffic/camera frame. Classify into one of: accident, speed_sensor, hazard.
Return ONLY valid JSON, no markdown or extra text:
{
  "event_type": "one of: accident, speed_sensor, hazard",
  "has_police": true or false,
  "has_accident": true or false,
  "hazard_level": 1-10 (10 = severe),
  "description": "One short sentence e.g. 'Red SUV collision with barrier' or 'Normal traffic flow'"
}"""


def analyze_frame(image_path: Path) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        return _mock_response(image_path.name)
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        b64_image = base64.b64encode(raw).decode("utf-8")
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}},
                    {"text": PROMPT},
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }
        for model in GEMINI_MODELS:
            for version in ("v1beta", "v1"):
                url = f"{GEMINI_BASE}/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                try:
                    resp = httpx.post(url, json=payload, timeout=30.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if text.startswith("```"):
                            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
                        return json.loads(text)
                except Exception:
                    continue
        return _mock_response(image_path.name)
    except Exception:
        return _mock_response(image_path.name)


def _mock_response(name: str) -> dict[str, Any]:
    return {
        "has_police": "police" in name.lower(),
        "has_accident": "accident" in name.lower() or "crash" in name.lower(),
        "hazard_level": 7 if "accident" in name.lower() or "crash" in name.lower() else 3,
        "description": f"Frame: {name}",
    }


def extract_frames_from_video(video_path: Path, interval_sec: int = 5, out_dir: Path | None = None) -> list[Path]:
    try:
        import cv2
    except ImportError:
        return []
    out = out_dir or video_path.parent / "frames"
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(fps * interval_sec))
    frame_paths = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            path = out / f"{video_path.stem}_frame_{idx}.jpg"
            cv2.imwrite(str(path), frame)
            frame_paths.append(path)
        idx += 1
    cap.release()
    return frame_paths


def list_feed_sources() -> list[tuple[str, Path]]:
    if not FEEDS_DIR.exists():
        return []
    out = []
    for p in sorted(FEEDS_DIR.iterdir()):
        if p.suffix.lower() in (".mp4", ".avi", ".mov", ".jpg", ".jpeg", ".png"):
            out.append((p.stem, p))
    return out


def collect_frames_from_feeds(interval_sec: int = 5) -> list[tuple[str, Path]]:
    sources = list_feed_sources()
    result = []
    for feed_id, path in sources:
        if path.suffix.lower() in (".jpg", ".jpeg", ".png"):
            result.append((feed_id, path))
        else:
            frames = extract_frames_from_video(path, interval_sec=interval_sec)
            if frames:
                result.append((feed_id, frames[0]))
    return result
