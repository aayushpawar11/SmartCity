"""
Wizard of Oz: sample frames from video/image feeds and send to Gemini Vision.
Returns structured JSON for storage and map pins.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import FEEDS_DIR, GEMINI_API_KEY

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
        model = genai.GenerativeModel("gemini-1.5-flash")  # flash is free and fast
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
        # Remove markdown code block if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return _mock_response(image_path.name)


def _mock_response(name: str) -> dict[str, Any]:
    """Fallback when no API key or on error - so demo still runs."""
    return {
        "has_police": "police" in name.lower(),
        "has_accident": "accident" in name.lower() or "crash" in name.lower(),
        "hazard_level": 7 if "accident" in name.lower() or "crash" in name.lower() else 3,
        "description": f"Frame: {name}",
    }


def extract_frames_from_video(video_path: Path, interval_sec: int = 5, out_dir: Path | None = None) -> list[Path]:
    """Extract one frame every interval_sec. Requires opencv. Saves to out_dir or same dir as video."""
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
    """List video or image files in FEEDS_DIR. Returns (feed_id, path) for each file."""
    if not FEEDS_DIR.exists():
        return []
    out = []
    for p in sorted(FEEDS_DIR.iterdir()):
        if p.suffix.lower() in (".mp4", ".avi", ".mov", ".jpg", ".jpeg", ".png"):
            out.append((p.stem, p))
    return out


def collect_frames_from_feeds(interval_sec: int = 5) -> list[tuple[str, Path]]:
    """Returns (feed_id, frame_path) for one frame per feed (videos: extract one; images: use as-is)."""
    sources = list_feed_sources()
    result = []
    for feed_id, path in sources:
        if path.suffix.lower() in (".jpg", ".jpeg", ".png"):
            result.append((feed_id, path))
        else:
            frames = extract_frames_from_video(path, interval_sec=interval_sec)
            if frames:
                result.append((feed_id, frames[0]))  # use first extracted frame for MVP
    return result
