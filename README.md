# SmartCity Safety — Hackathon MVP

**Wizard of Oz cameras + Gemini Vision + vector search + real-time map + voice alerts.**

- **SafetyKit angle:** Detect hazards (accidents, police, flooding) and voice-alert the driver.
- **Actian VectorAI angle:** Event descriptions → embeddings → semantic search (“Show me all accidents involving trucks”).
- **Free stack:** Gemini (free tier), Web Speech API (no key), Leaflet + OSM (free), SQLite when Actian not available.

---

## Quick start (no API keys)

**Backend:** Python 3.8+ is fine. (Gemini/OpenCV need 3.9+; without them you get demo/mock behavior.)

1. **Backend**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

2. **Seed demo events** (so the map has data):
   ```bash
   curl -X POST http://localhost:8000/seed
   ```

3. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open **http://localhost:3000**. You should see the map with 5 demo pins. Click a pin for details. Use the search bar for semantic search (e.g. “accidents” or “police”).

---

## With Gemini (free) for real analysis

1. Get a free API key: [Google AI Studio](https://aistudio.google.com/apikey).
2. In `backend`, create `.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```
3. Add **feed sources**: put video files (`.mp4`) or images (`.jpg`) in `backend/feeds/`. Name them for the Wizard of Oz (e.g. `accident.mp4`, `police.jpg`, `traffic.mp4`).
4. Trigger analysis:
   ```bash
   curl -X POST http://localhost:8000/analyze
   ```
   This extracts frames, sends them to Gemini Vision, stores events + embeddings, and returns new events (frontend can use these for voice alerts).

---

## With Actian VectorAI (when provided)

1. Set in `backend/.env`:
   ```env
   ACTIAN_CONNECTION_STRING=your_connection_string
   ```
2. Implement `backend/actian_adapter.py`: `insert_embedding_actian()` and `search_actian()` using the hackathon SDK/Docker API. The app will use Actian for vector storage and search instead of SQLite.

---

## Navigation (GPS + hazard alerts + reroute)

- **Get directions:** Enter From (lat, lng) and To (lat, lng) in the **Navigate** panel, then **Get directions**. The route is drawn on the map (OSRM, free).
- **Simulated drive:** The app moves a "car" along the route every few seconds. Use **End** to stop.
- **Hazard alert:** If a crash or police event is within ~0.4 km of the route and within 3 miles ahead, a popup appears: *"Hazard X miles ahead: [description]"* with **Reroute** and **Continue**.
- **Reroute:** **Reroute** fetches a new route from your *current* position to the same destination and replaces the route (autonomous reroute). **Continue** dismisses the alert and keeps going.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /events` | List events for the map (poll every 5s). |
| `GET /events/{id}` | Event detail (for popup). |
| `GET /route?from_lat=&from_lng=&to_lat=&to_lng=` | Driving route (OSRM). Returns `coordinates`, `distance_meters`, `duration_seconds`. |
| `GET /search?q=...` | Semantic search over event descriptions (vector similarity). |
| `POST /analyze` | Run frame capture + Gemini on `feeds/`, store events. |
| `POST /seed` | Insert 5 demo events (no feeds/Gemini needed). |
| `GET /image?path=...` | Serve frame image (path relative to backend). |

---

## Notifications & voice alerts

1. **Have events to notify about:** Run `curl -X POST http://localhost:8000/seed` so the backend has hazard events. New events (from seed or from `POST /analyze`) with hazard_level ≥ 6 trigger notifications.
2. **Enable alerts in the app:** Click **Enable alerts** in the header. This (a) asks for browser notification permission, (b) turns on voice (TTS) by playing a test phrase so the browser allows future speech.
3. **What you get:**
   - **In-app toasts:** New hazards show a toast (bottom-right) for a few seconds.
   - **Browser notifications:** If you allowed permission, you get a system notification even when the tab is in the background.
   - **Voice:** When alerts are enabled, new hazards are read out via the Web Speech API.
4. **Optional:** Add ElevenLabs in `frontend/src/lib/tts.ts` and set `ELEVENLABS_API_KEY` for a different voice.

---

## Project layout

```
SmartCity/
├── backend/           # Python FastAPI
│   ├── main.py        # API + CORS + image serving
│   ├── analyze.py     # Frame capture + Gemini Vision
│   ├── pipeline.py    # Run analysis, store events, fake coords
│   ├── store.py       # SQLite events + optional embedding column
│   ├── search.py      # Vector search (Actian or in-memory)
│   ├── embeddings.py  # Gemini embedding API
│   ├── actian_adapter.py  # Stub for Actian VectorAI
│   ├── config.py
│   ├── feeds/         # Put videos or images here
│   └── data/          # SQLite DB (auto-created)
├── frontend/          # Next.js + Leaflet
│   └── src/
│       ├── app/
│       ├── components/  # Map, SearchBar
│       ├── lib/        # TTS
│       └── types/
├── .env.example
└── README.md
```

---

## Demo flow for judges

1. **Safety:** Open map → click a red (high-hazard) pin → show Gemini’s description. Trigger `POST /analyze` with a clip named `accident` in `feeds/`; new event appears and (if enabled) a voice alert plays.
2. **Actian:** Show search: type “accidents involving trucks” or “flooding” → results are event pins from vector similarity (or from Actian when connected).
3. **Figma:** Use the same map/data in a Figma Make flow for heatmaps or dashboards.

---

## License

MIT
