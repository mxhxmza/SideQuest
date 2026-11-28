# SideQuest: route-aware stop planner (Singapore)

**Live app:** https://side-quest-wheat.vercel.app

You can watch the Demo video using this link: 
[![Watch the demo](https://youtu.be/UfAIhn0KbrA)]


Tell SideQuest where you're going and what you need on the way, in plain words:

> *"mosque at Maghrib, then a halal dinner and petrol"*
> *"church before 10am, then flowers, a cake from a bakery, a pharmacy, an ATM and petrol"*
> *"Hindu temple and a vegetarian lunch"*

You get back a timeline of the whole trip. Each stop's options are ranked by the **extra minutes they add to your drive**, not by distance from a pin. Opening hours are checked for when you'll actually arrive, two errands in the same mall get merged into one stop, and one tap sends the route to Google Maps.

It understands 28 place types: places of worship for every faith mapped in Singapore (church, Buddhist, Hindu and Taoist temples, gurdwara, synagogue, mosque, surau), food, and everyday errands. It also knows 16 cuisines (Italian, Japanese, Chinese, Indian, Korean and more), diets (halal, vegetarian, vegan) and times like "around 1pm", "before 10am", "45 min in" or "at Asar". Anything it doesn't recognise becomes a place-name search. Muslim prayer times (MUIS method) show up on the route only when you ask for a mosque, a surau or a prayer time. Other trips never see them.

The whole thing runs on a $0 stack with no card-gated services.

## Why not just use Google Maps, or ask an AI?

**Google Maps** can search along your route, but only one thing at a time. You search for a mosque and add it, then search for food and add that, then petrol. Working out when Maghrib starts, whether the restaurant is still open when you get there, and what order makes sense is left to you.

**A general chatbot** can write a plan, but it isn't built for this. I gave Gemini the same 6-stop Sunday trip as SideQuest (27 Nov 2026, logged-out web version):

| | Gemini | SideQuest |
|---|---|---|
| Time to answer | about 41 s (over 2 min on another try) | about 7 s |
| Stops | most given as "this **or** that" | one place per stop, alternatives ranked underneath |
| Same question twice | two different plans | the same plan |
| Output | text | timeline + map + one tap to Google Maps |

To be fair, Gemini's second plan had a smart idea (doing four errands inside one mall), and that's now on the roadmap below.

## How it works

The planner (`POST /api/plan`) runs a 10-stage pipeline:

1. **Parse**: plain text becomes typed stop requests (category, cuisine, diet, time window)
2. **Route**: base A→B route with a timestamp at every vertex
3. **Timeline**: where you'll be, and when, along the route
4. **Windows**: each timed stop maps to the stretch of road you'll be on at that time
5. **Search**: candidate places in a buffer around that stretch (OSM data in SQLite + R*Tree)
6. **Estimate**: a quick detour estimate for every candidate
7. **Verify**: real routing for the top candidates
8. **Score**: detour minutes plus penalties (closed at your ETA, outside your window, weak diet evidence…)
9. **Combine**: stops in the same mall or shop get merged
10. **Hand-off**: a keyless Google Maps link with your stops as waypoints

`core/` is pure logic with no I/O. Providers (routing, geocoding, places, LLM parsing) plug in through interfaces, and each one has a fallback. More detail in [docs/DESIGN.md](docs/DESIGN.md), and the trade-offs behind each choice are in [docs/DECISIONS.md](docs/DECISIONS.md).

The web app has two pages: a landing page at `/` that explains the app and its architecture, and the planner at `/plan`. The planner has a light game layer (stars per trip, XP and levels, 17 badges, optional sound effects). All of it is computed in the browser and kept in `localStorage` (`frontend/src/lib/game.ts`).

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

Copy `.env.example` to `.env` at the repo root to configure providers. **No credentials are needed** for drive, walk or cycle: routing falls back to keyless OSRM servers and geocoding to Photon (DECISIONS D11).

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

The OneMap fixtures in `backend/tests/fixtures/onemap/` are real responses recorded on 2026-11-26. Re-record them any time with the command above.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/parse` | `{text, departure_time?, backend?}` → `{backend_used, stops[], warnings[]}` |
| POST | `/api/plan` | `TripRequest` (+ `pinned: {stop_id: osm_id}`) → `TripPlan` |
| GET | `/api/prayer-times?lat&lng&date&asr=shafii` | MUIS times |
| GET | `/api/geocode?q=` | `[{name, address, lat, lng, source}]` |
| GET | `/api/categories` | stop categories (for the chip editor) |
| GET | `/api/cuisines` | cuisine filters for food stops |
| GET | `/api/health` | providers, POI DB version/date |

## Deploy ($0)

- **Backend on Render Free (Docker):** `render.yaml` blueprint. The image build downloads the OSM extract and bakes `pois.sqlite` in (ephemeral disk, D1). Set `CORS_ORIGINS` to your Vercel URL and, optionally, your OneMap credentials.
- **Frontend on Vercel Hobby:** project root `frontend/`, build `npm run build`, output `dist`, env `VITE_API_URL=https://<your-render-service>.onrender.com`.

## Limitations

**Data**
- Cuisine and diet tags in OpenStreetMap are patchy. Only a few places carry `diet:halal`, and certifications aren't in OSM at all. Weak hints are labelled, and the app never claims a place is certified.
- Many places have no opening hours in OSM, so you'll often see "hours unknown".
- Small prayer rooms and shrines are rarely mapped.
- Places data is a snapshot (see `/api/health` for the date), so new or closed shops lag behind.

**Planning**
- The multi-stop pass is greedy (D7). It's explainable, but it isn't globally optimal. You can pin a different option with "Use this" and the rest of the trip re-plans.
- Transit detours are estimates (headway / 2). Google Maps ignores waypoints for transit, so you get one link per leg instead.
- Errands are only grouped when they're in the same building. It won't yet say "park once and walk to the next mall".

**Hosting and scope**
- The backend is on Render's free tier, which sleeps when idle. The first plan after a quiet spell can take up to a minute while it wakes up.
- Singapore only, for now.

## Known issues

Found while testing the live app on 27 Nov 2026:

- **"Bubble tea" becomes a second café.** "…coffee, … bubble tea…" books the same café twice. Bubble tea needs its own category or a name search.
- **Clock times can be missed with no warning.** Leaving Jurong Point at 08:30 for Changi Airport with "church before 10am" placed the church at 11:04. "Italian lunch at 11:30" on a trip that ends before then was placed at 10:18. A timed stop that can't be met should say so.
- **"Mosque at Asr" can land before Asr.** NTU → Changi Airport leaving 15:00 put the mosque at 15:50, while Asr begins at 16:17.
- **A place shown as closed can still be chosen.** On NTU → Tampines Mall (Sunday 08:30) the planned ATM is tagged "closed" at the ETA. ATMs should probably skip opening-hours checks, or a closed pick should fall to the next option.

## Roadmap

### Next: fixes and quick wins
- Fix the known issues above, and add each one to `eval/cases.jsonl` so it stays fixed.
- Warn clearly when a timed stop can't fit the trip, rather than placing it anyway.
- "Park once" clusters: if several errands sit in or next to one mall near the destination, group them as a single walking stop.

### Later: paid APIs (only once usage justifies it)
The free providers stay as fallbacks. Paid ones slot in behind the same interfaces in `app/providers`:

| Upgrade | What it adds |
|---|---|
| Google Places API | fresher places, much better opening-hours coverage, ratings and reviews |
| Google Routes API | live, traffic-aware detour times |
| Hosted LLM for parsing | understands almost anything you type ("somewhere to charge my EV", "bubble tea"), not just the built-in lexicon |
| Official halal certification data (MUIS) | real certification instead of OSM hints |

### Scaling
- **Always-on backend** (paid Render or similar) so there's no cold start.
- **Shared cache** (e.g. Redis) for routes, geocodes and places, so popular trips cost fewer API calls.
- **New regions:** a region is one config file in `app/regions/` plus its own POI database built by `scripts/import_osm.py`. Malaysia and the rest of Southeast Asia are the obvious next step.
- **Rate limiting and per-user quotas** once paid APIs are involved, to keep costs predictable.

### Product
- Accounts with saved trips and favourite places
- Multi-day trips and round trips
- A native mobile app (the PWA is already installable)
- Sharing a planned trip with friends or family

## Credits

Map data © OpenStreetMap contributors · tiles OpenFreeMap / OpenMapTiles · routing OneMap, OpenRouteService, OSRM · geocoding OneMap, Photon.

