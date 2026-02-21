import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Gemini (free tier: https://ai.google.dev)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Actian VectorAI (hackathon-provided; leave empty for local SQLite vector store)
ACTIAN_CONNECTION_STRING = os.getenv("ACTIAN_CONNECTION_STRING", "")
ACTIAN_ENABLED = bool(ACTIAN_CONNECTION_STRING)

# ElevenLabs (optional; we use Web Speech API by default for free)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Path to folder of videos or images (Wizard of Oz feeds). Default: backend/feeds
_backend = Path(__file__).resolve().parent
FEEDS_DIR = Path(os.getenv("FEEDS_DIR", str(_backend / "feeds")))
# Frame capture interval in seconds
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", "5"))

# SQLite path when not using Actian
DB_PATH = Path(os.getenv("DB_PATH", "data/events.db"))
