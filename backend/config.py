import os
from pathlib import Path

from dotenv import load_dotenv

_backend = Path(__file__).resolve().parent
_project_root = _backend.parent
load_dotenv(_project_root / ".env")
load_dotenv(_backend / ".env", override=True)

# Gemini (free tier: https://ai.google.dev)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Actian VectorAI DB (Docker on localhost:50051)
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))
ACTIAN_CONNECTION_STRING = os.getenv("ACTIAN_CONNECTION_STRING", "")
ACTIAN_ENABLED = bool(ACTIAN_HOST)

# OSRM routing
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://router.project-osrm.org")

# Sphinx CLI
SPHINX_ENABLED = os.getenv("SPHINX_ENABLED", "false").lower() in ("true", "1", "yes")

# ElevenLabs (optional; we use Web Speech API by default for free)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Path to folder of videos or images (Wizard of Oz feeds). Default: backend/feeds
FEEDS_DIR = Path(os.getenv("FEEDS_DIR", str(_backend / "feeds")))
# Frame capture interval in seconds
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", "5"))

# SQLite path
DB_PATH = Path(os.getenv("DB_PATH", "data/events.db"))
