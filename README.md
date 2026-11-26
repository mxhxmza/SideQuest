# SideQuest — Route-aware Stop Planner (Singapore)

Type your trip and the stops you want in plain words — *"halal lunch around 1pm, a mosque near Asr time,
somewhere to buy a phone charger"* — and get a timeline where every stop's options are ranked by
**extra minutes added to the trip**, with prayer times placed on the route, opening hours checked at
your ETA, combined stops (same mall), and a one-tap hand-off to Google Maps.

The web app has two pages: a landing page at `/` that explains what the app does and how it is built
(architecture, the 10-stage planning pipeline, provider fallbacks, scoring rules), and the planner at
`/plan`. The planner has a light game layer — stars per trip, XP and levels, 16 badges, optional sound
effects — computed in the browser from the plan and stored in `localStorage` only (`frontend/src/lib/game.ts`).

$0 stack, no card-gated services. Design: [docs/DESIGN.md](docs/DESIGN.md) · trade-offs: [docs/DECISIONS.md](docs/DECISIONS.md).

```
frontend/   React + TS + Vite + Tailwind + MapLibre (OpenFreeMap), PWA
backend/    FastAPI · app/core (pure logic) · app/providers (OneMap, ORS, OSRM, Photon, OSM SQLite, LLMs)
data/       (gitignored) Geofabrik extract + pois.sqlite built by backend/scripts/import_osm.py
```

## Run locally

Prereqs: Python 3.11, Node 20+.

```bash
# 1. backend
cd backend
python -m venv .venv && .venv/Scripts/activate        # (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-import.txt -r requirements-dev.txt
python scripts/import_osm.py        # one-off: downloads ~250 MB, builds data/pois.sqlite (~4-5 min)
uvicorn app.main:app --port 8000

# 2. frontend (new terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api to :8000)
```

Copy `.env.example` to `.env` at the repo root to configure providers. **No credentials are required**
for drive / walk / cycle: routing falls back to keyless OSRM servers and geocoding to Photon (DECISIONS D11).

| Feature | Needs |
|---|---|
| Public-transport routing | OneMap account → `ONEMAP_EMAIL`, `ONEMAP_PASSWORD` (free, [onemap.gov.sg](https://www.onemap.gov.sg/apidocs/)). The API needs a password of **at least 12 characters**, even though its error message says 8. |
| OneMap search (better SG addresses) | same OneMap account |
| ORS fallback | `ORS_API_KEY` (free) |
| LLM parsing | `LLM_BACKEND=ollama` with a local Ollama, or `openai_compat` + `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` (e.g. Groq) |

`GET /api/health` shows which providers are active and the OSM data date.

## Tests & eval

```bash
cd backend && python -m pytest                       # core, planner (fake providers), providers, API
python eval/run_eval.py --backend rules -v           # NL parsing eval (also: ollama, openai_compat)
python tests/record_onemap.py --record               # refresh OneMap fixtures (needs credentials)
cd frontend && npm test && npm run build             # Vitest (deep links, formatting) + typecheck/build
```

The OneMap fixtures in `backend/tests/fixtures/onemap/` are real responses recorded on 2026-11-26 (re-record any time with the command above).

## API

| Method | Path | |
|---|---|---|
| POST | `/api/parse` | `{text, departure_time?, backend?}` → `{backend_used, stops[], warnings[]}` |
| POST | `/api/plan` | `TripRequest` (+ `pinned: {stop_id: osm_id}`) → `TripPlan` |
| GET | `/api/prayer-times?lat&lng&date&asr=shafii` | MUIS times |
| GET | `/api/geocode?q=` | `[{name, address, lat, lng, source}]` |
| GET | `/api/categories` | stop categories (for the chip editor) |
| GET | `/api/health` | providers, POI DB version/date |

## Deploy ($0)

- **Backend — Render Free (Docker):** `render.yaml` blueprint. The image build downloads the OSM extract and
  bakes `pois.sqlite` in (ephemeral disk, D1). Set `CORS_ORIGINS` to your Vercel URL and, optionally, OneMap creds.
- **Frontend — Vercel Hobby:** project root `frontend/`, build `npm run build`, output `dist`,
  env `VITE_API_URL=https://<your-render-service>.onrender.com`.

## Honest limitations

Halal data in OSM is sparse and MUIS certification isn't in OSM — weak hints are labelled and the app never claims
certification. Mall prayer rooms are rarely mapped. Many places lack opening hours ("hours unknown"). Transit
detours are estimates (headway/2). Google Maps ignores waypoints for transit, so per-leg links are offered.
The greedy multi-stop pass (D7) is explainable but not globally optimal — pin alternatives with "Use this".

Map data © OpenStreetMap contributors · tiles OpenFreeMap / OpenMapTiles.
