"""
Analysis layer:
  - analyze_frame(): legacy feed-based Gemini Vision (unchanged)
  - analyze_frame_with_gemini(): new structured incident classifier
  - run_sphinx_decision_engine(): Sphinx CLI reasoning over incident data
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from config import FEEDS_DIR, GEMINI_API_KEY, SPHINX_ENABLED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# New: Structured incident classification from raw image bytes
# ---------------------------------------------------------------------------

INCIDENT_PROMPT = """You are a traffic incident classifier analyzing a camera frame.
Classify what you see. Return ONLY valid JSON, no markdown:
{
  "event_type": "one of: accident, construction, stalled_vehicle, flooding, police_activity, normal_traffic, debris, fire",
  "confidence": 0.0 to 1.0,
  "vehicles_detected": integer count of vehicles visible,
  "blocked_lanes": integer count of lanes blocked (0 if none),
  "severity": "one of: none, low, moderate, high, critical",
  "description": "One sentence describing the scene"
}"""


async def analyze_frame_with_gemini(image_bytes: bytes) -> dict:
    """Send image bytes to Gemini Flash, return structured incident JSON."""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY, returning fallback")
        return _incident_fallback()
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [
                {"mime_type": "image/jpeg", "data": image_bytes},
                INCIDENT_PROMPT,
            ],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(text)
        logger.info("Gemini classified: %s (%.2f)", result.get("event_type"), result.get("confidence", 0))
        return result
    except Exception as e:
        logger.error("Gemini analysis failed: %s", e)
        return _incident_fallback()


def _incident_fallback() -> dict:
    return {
        "event_type": "unknown",
        "confidence": 0.3,
        "vehicles_detected": 0,
        "blocked_lanes": 0,
        "severity": "low",
        "description": "Unable to classify — Gemini unavailable",
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
            f"Severity: {payload.get('severity', 'unknown')}, "
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
    severity = payload.get("severity", "low")

    if payload.get("is_false_positive"):
        return {"action": "dismiss", "final_confidence": confidence * 0.3, "explanation": "Likely false positive based on similar incidents"}

    if severity in ("high", "critical") and confidence > 0.7:
        return {"action": "reroute", "final_confidence": confidence, "explanation": f"High severity {payload.get('event_type', 'incident')} with strong confidence"}

    if severity == "moderate" or confidence > 0.5:
        return {"action": "monitor", "final_confidence": confidence, "explanation": "Moderate incident — monitoring recommended"}

    return {"action": "monitor", "final_confidence": confidence, "explanation": "Low severity — continue monitoring"}


# ---------------------------------------------------------------------------
# Legacy: feed-based frame analysis (kept for /analyze endpoint)
# ---------------------------------------------------------------------------

PROMPT = """Analyze this traffic/camera frame. Focus on safety: accidents, police, hazards, flooding, fire, road rage, unsafe pedestrians.
Return ONLY valid JSON, no markdown or extra text:
{
  "has_police": true or false,
  "has_accident": true or false,
  "hazard_level": 1-10 (10 = severe),
  "description": "One short sentence e.g. 'Red SUV collision with barrier' or 'Normal traffic flow'"
}"""


def analyze_frame(image_path: Path) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        return _mock_response(image_path.name)
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        with open(image_path, "rb") as f:
            data = f.read()
        response = model.generate_content(
            [
                {"mime_type": "image/jpeg", "data": data},
                PROMPT,
            ],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(text)
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
