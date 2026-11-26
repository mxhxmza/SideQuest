# Route-aware Stop Planner — Design

Status: implemented end to end (M1–M6 functionality; M7 deploy config written, not yet deployed). Region: Singapore. Budget: $0. No card-gated services.
Later changes to this plan are recorded in DECISIONS.md D11–D14 (keyless fallbacks, two extra scoring terms, matrix-based exact detours, shrine exclusion).

## 1. What it does

The user enters origin, destination, travel mode and departure time, then types the stops they want in plain language:

> "halal lunch around 1pm, a mosque near Asr time, somewhere to buy a phone charger"

The app returns a **timeline** of the trip. Each requested stop has ranked options, sorted by **extra minutes added to the trip** rather than straight-line distance. The user picks options and opens the trip in Google Maps through a keyless deep link.

## 2. Free stack (all $0, no card)

| Concern | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind, `vite-plugin-pwa` | Mobile-first, installable |
| Map | MapLibre GL JS + OpenFreeMap `liberty` style | No key. OSM + OpenFreeMap attribution always visible |
| Routing (primary) | OneMap Routing (SLA) | Free account; token via `getToken`, ~3-day JWT, auto-refreshed |
| Routing (fallback) | OpenRouteService free key | drive / walk / cycle only, **no transit** |
| Geocoding | OneMap Search | Origin/destination autocomplete |
| Places | OSM Singapore extract → SQLite + R\*Tree | Imported once by script, refreshable; no runtime Overpass calls |
| Opening hours | `opening-hours-py` (parser for the OSM `opening_hours` tag) | "Hours unknown" when the tag is missing or unparseable |
| Prayer times | `adhanpy`, `CalculationMethod.SINGAPORE` (MUIS) | Asr: Shafi'i default, Hanafi toggle |
| NL parsing | `rules` (default) / `ollama` / `openai_compat` | All behind `LLMProvider` |
| Backend | Python 3.11 + FastAPI + Pydantic v2 | |
| Cache | SQLite (`cache.sqlite`) | Route/geocode responses keyed by request hash with TTL |
| Hosting | Vercel Hobby (frontend), Render Free (backend, Docker) | See §11 |

## 3. Architecture

```
┌──────────────── frontend (Vercel) ───────────────┐
│ TripForm → StopInput(NL) → Timeline + Map → Stop │
│ detail → "Open in Google Maps" (URL deep link)   │
└───────────────┬──────────────────────────────────┘
                │ JSON over HTTPS
┌───────────────▼──────────── backend (Render) ────┐
│ api/  (FastAPI routes: parse, plan, prayer, geo) │
│   │                                              │
│ core/ (pure logic, no I/O, fully unit-tested)    │
│   timeline · segments · detour · scoring ·       │
│   combine · prayer · hours · deeplink · planner  │
│   │                                              │
│ providers/ (interfaces + implementations)        │
│   RoutingProvider   → OneMap | ORS               │
│   GeocodingProvider → OneMap                     │
│   PlacesProvider    → OsmSqlite                  │
│   LLMProvider       → Rules | Ollama | OpenAI-compat
│   │                                              │
│ regions/singapore.py (bbox, tz, prayer method,   │
│   default providers, mode speeds, buffers)       │
│ cache.py (SQLite TTL cache wrapping providers)   │
└──────────────────────────────────────────────────┘
          data/pois.sqlite  ←  scripts/import_osm.py  ←  Geofabrik .pbf
```

**Rule:** `core/` never imports a concrete provider. `planner.py` receives providers through constructor injection. Google, Mapbox or another region becomes a new class plus a config switch.

### Provider interfaces (sketch)

```python
class RoutingProvider(Protocol):
    def route(self, origin: LatLng, dest: LatLng, mode: Mode,
              depart: datetime) -> Route: ...          # geometry + per-vertex cumulative seconds
    def supports(self, mode: Mode) -> bool: ...

class GeocodingProvider(Protocol):
    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]: ...

class PlacesProvider(Protocol):
    def query(self, bbox: BBox, filters: list[OsmFilter]) -> list[Place]: ...

class LLMProvider(Protocol):
    name: str
    def parse(self, text: str, ctx: ParseContext) -> list[StopRequest]: ...
```

### Region config

`regions/singapore.py` holds the bbox, timezone `Asia/Singapore`, prayer method (MUIS), default routing/geocoding providers, Geofabrik URL plus clip polygon, mode speeds and buffer sizes. A new region adds one file and its own POI DB.

## 4. Data model (Pydantic)

```
TripRequest   origin: Point, destination: Point, mode: drive|walk|cycle|transit,
              departure_time: datetime (tz-aware), stops: StopRequest[],
              prefs: { asr_method: shafii|hanafi, prayer_method: str }

StopRequest   id, query (original text), category (enum key into tag dictionary),
              osm_filters: OsmFilter[], name_keywords: str[],
              time_window: { type: minutes_in|clock_time|prayer|any, value, tolerance_min },
              constraints: { open_at_eta: bool, dietary: [halal|vegetarian|...] },
              dwell_min (default per category: meal 45, prayer 20, shop 15)

PlaceCandidate osm_id, name, lat, lng, tags, open_at_eta: true|false|unknown,
              detour_min, detour_exact: bool, eta, score, score_breakdown{},
              matched_stop_ids[], evidence[] (e.g. "diet:halal=yes", "name contains 'halal'")

TripPlan      route: {geometry, duration_s, distance_m, mode, provider},
              stops: [{ request, eta_window, candidates: PlaceCandidate[] (top 5) }],
              prayer_times: [{ name, time, position: Point, route_fraction, stop_id? }],
              total_added_min, arrival_eta, gmaps_url, warnings[]
```

`dwell_min` is an addition to the spec. Without it, ETAs after a lunch stop would be wrong by about 45 minutes. See DECISIONS.md.

## 5. Core algorithm

### 5.1 Route and timeline
1. `RoutingProvider.route()` returns a polyline plus total duration. OneMap drive/walk/cycle give one geometry. Transit gives itinerary legs (WALK, BUS, SUBWAY), and the legs are concatenated.
2. **Cumulative time per vertex.** The leg duration is spread over its vertices in proportion to segment length. For transit, each leg's own duration is used, so waiting time stays inside the leg it belongs to. Result: `t[i]` = seconds from departure at vertex `i`.
3. `position_at(t)` and `time_at(fraction)` interpolate along the arrays. Everything else builds on these two functions.

### 5.2 Time window → route segment
| Window type | Target time | Example |
|---|---|---|
| `minutes_in` | depart + value | "45 min in" |
| `clock_time` | value on trip date | "around 1pm" |
| `prayer` | prayer start (computed at the route position at that time) | "at Asr", "Asr anytime until 6pm" |
| `any` | whole route | "somewhere to buy a charger" |

Segment = route portion between `target − tolerance` and `target + tolerance`, clipped to [0, duration]. Default tolerance is ±20 min, or prayer start → +60 min for prayer windows (prayer start → `until` when given, capped at the prayer's end). The segment starts one **lead** earlier — the one-way time to a place at the buffer's edge (~13 min on foot for transit/walk, ~5 min driving) — because the window applies to *arriving at the place*, not to leaving the route (D19). A prayer can't be prayed before it starts: arriving early means waiting, and the wait counts as minutes added. A target outside the trip produces a warning and is clamped to the start or end of the route.

### 5.3 Query → OSM filters
`core/tags.py` holds a dictionary: category key → OSM filters + name keywords + default dwell. Examples:

| Category | OSM filters | Name/cuisine hints |
|---|---|---|
| `mosque` | `amenity=place_of_worship` + `religion=muslim` | "masjid", "mosque" |
| `prayer_room` | `amenity=place_of_worship` + `religion=muslim` (incl. indoor nodes); exact tagging confirmed against SG data in M4 | "surau", "musolla", "musalla", "prayer room" |
| `halal` (dietary modifier) | `diet:halal=yes|only` | name "halal", cuisine `malay`/`indonesian`/`middle_eastern`/`turkish`; brands in a curated list |
| `meal` | `amenity=restaurant|fast_food|food_court|cafe` | |
| `charger` | `shop=electronics|mobile_phone|computer` | "Challenger", "Best Denki", "Courts" |
| `atm`, `toilet`, `petrol`, `pharmacy`, `supermarket` … | standard tags | |

Parsers (rules or LLM) output a **category from a fixed enum**. Tag mapping is deterministic code. An LLM can't invent tags, and the evaluation stays fair across backends.

### 5.4 Spatial query
- Buffer: 800 m for walk/transit (around transit stops only, see 5.5), 2 km for drive, 1.2 km for cycle. Values live in the region config.
- Query the R\*Tree by the segment's bbox expanded by the buffer, then filter exactly by perpendicular distance to the segment polyline. Coordinates go through a local equirectangular projection; the error is negligible at Singapore's size, so pyproj isn't needed.
- For each place, record `nearest_vertex_idx`, `offset_m` (distance to the route) and `along_t` (route time at the nearest point). `along_t` becomes the base ETA.

### 5.5 Detour estimate (cheap first)
```
drive/cycle/walk:  detour ≈ 2 · offset_m · circuity(1.3) / mode_speed
transit:           detour ≈ 2 · walk(offset from nearest stop/station) + expected_wait(headway/2)
                   (only stops/stations where the itinerary actually halts are eligible
                    hop-off points: legs' intermediate stops from OneMap pt output)
```
Mode speeds: drive 30 km/h urban average, cycle 15, walk 4.8. Then **exact** detour for the top 3 per stop only:
`route(prev → place) + route(place → next) − route(prev → next)`, where prev and next are the neighbouring route points around the place. Transit uses OneMap pt for the re-board leg. Calls are cached, run in parallel up to a semaphore of 4, and use a token bucket below OneMap's per-minute limit. If a call fails, the estimate is kept and marked `detour_exact=false`.

### 5.6 Scoring (lower is better, in minutes, so it's explainable)
```
score = detour_min
      + 60  if open_at_eta == false and constraint open_at_eta   (closed → effectively bottom)
      +  3  if open_at_eta == unknown
      + 0.5 · max(0, |eta − target| − tolerance)                 (outside window)
      +  2  if no name
      +  5  if dietary requirement only met by a name/cuisine hint (weak evidence)
      − combine_bonus
```
The UI shows `score_breakdown` so users can see why one place ranks above another. A place with no evidence for a required dietary constraint is excluded, not penalised.

### 5.7 Combined stops
Two kinds:
1. **Same POI** matches several requests, e.g. a food court with a prayer room tag.
2. **Container**: the import marks POIs inside a `shop=mall` or large `building` polygon with `parent_id`. A mall "covers" request R if it contains a matching POI.

A combined candidate is valid if its ETA falls within every covered request's window. Its bonus is the **actual minutes saved**:
`combine_bonus = Σ(best standalone detour of each covered request) − combined detour`. Dwell times are summed.

### 5.8 Multi-stop ETA cascade
Stops are processed in order of target time. After the top choice for stop *k* is picked, every later timestamp shifts by `detour_k + dwell_k`. Later segments and prayer times are recomputed from the shifted clock, while positions stay on the original route geometry. This greedy pass is simple and explainable. A globally optimal ordering is a non-goal (see DECISIONS.md).

### 5.9 Prayer awareness
1. Compute today's times at the origin. In Singapore they differ by about 2 minutes across the island, so origin times are fine for now. A per-position recompute is kept for future regions.
2. Every prayer whose start falls between departure and (adjusted) arrival goes into `prayer_times`. Prayers whose window is already open at departure are listed with the note "window open now".
3. `position_at(prayer_time)` gives where the user will be.
4. If the user asked for a prayer stop, that stop's window is [prayer start, +60 min] (or until the time they gave), searched from one lead earlier on the route (§5.2). Otherwise the timeline shows the prayer as an **info row** with a "suggest mosques here" button that adds a `prayer` StopRequest.
5. Mosques come from OSM, which covers Singapore's ~70 mosques well. Prayer rooms (surau/musolla in malls) are poorly covered (see §9).

### 5.10 Opening hours
`hours.py` evaluates the tag at the place's ETA in `Asia/Singapore` with `opening-hours-py`. Results are `true`, `false` or `unknown` (missing tag or parse error). The UI shows "hours unknown" in grey and never hides these places.

## 6. Natural-language parsing

Flow: `text → LLMProvider.parse() → Pydantic validation → tag mapping`. If a backend fails validation or times out, the request falls back to `rules`, and the response notes which backend was used.

- **rules (default):** split into clauses on `,` `;` "and" "then". Each clause goes through a keyword lexicon → category (with synonyms: zohor/zuhur/dhuhr, asar/asr, isyak/isha, surau, musolla, "pray"), a dietary lexicon (halal, vegetarian…) and time regexes ("around 1pm", "at 13:30", "45 min in", "after an hour", "at Asr", "before Maghrib").
- **ollama:** small local model (e.g. `qwen2.5:3b` or `llama3.2:3b`) using Ollama's JSON-schema `format` so output is constrained to the schema. Not installed on this machine yet; optional.
- **openai_compat:** one client for any OpenAI-compatible free tier. It's set by `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`. Works with Groq (free key, no card) and Gemini's OpenAI-compatible endpoint. Note: Google's free tier may use prompts to improve products.
- **Eval:** `eval/cases.jsonl` holds 20+ cases of text → expected `[{category, dietary, window.type, window.value}]`. `eval/run_eval.py --backend rules|ollama|openai_compat` reports per-field and exact-match accuracy.

## 7. API

| Method | Path | In → Out |
|---|---|---|
| POST | `/api/parse` | `{text, departure_time}` → `{backend_used, stops: StopRequest[]}` |
| POST | `/api/plan` | `TripRequest` (+ optional `pinned: {stop_id: osm_id}`) → `TripPlan` |
| GET | `/api/prayer-times?lat&lng&date&asr=shafii` | → `[{name, time}]` |
| GET | `/api/geocode?q=` | → `[{name, address, lat, lng}]` |
| GET | `/api/health` | provider status, POI DB version/date |

`pinned` lets the user swap a chosen option. The server then recomputes the cascade (5.8) so later ETAs stay correct.

## 8. Wireframes (mobile-first, described)

**Screen 1: Trip input**
```
┌─────────────────────────────┐
│ From  [NTU            ⌖]    │  OneMap autocomplete; ⌖ = current location
│ To    [Changi Airport   ]   │
│ [🚗 Drive][🚶][🚲][🚇 Transit]│
│ Depart [Today 12:30  ▾]     │
│ ┌─────────────────────────┐ │
│ │ halal lunch around 1pm, │ │  Free text
│ │ mosque near Asr, phone  │ │
│ │ charger                 │ │
│ └─────────────────────────┘ │
│ Parsed: [🍽 Halal meal ~13:00 ✎][🕌 Mosque @Asr ✎][🔌 Charger any ✎] │
│        [ Plan my trip ]     │  Chips are editable before planning
└─────────────────────────────┘
```
**Screen 2: Timeline + map** (map above, timeline in a bottom sheet; side by side on desktop)
```
┌──────────── map ────────────┐  Route line, numbered stop pins,
│  ①──②────🕌───③──── ✈      │  prayer-time markers on the route
└─────────────────────────────┘
 12:30 ● Depart NTU
 13:02 ① Halal meal   (restaurant in Jurong Point) · +6 min · open ✓ [▾ 4 more]
 15:51 🕌 Asr starts here (Bedok)         [suggest mosques]
 16:05 ② Mosque       Masjid Al-Ansar · +4 min
 13:02 ③ Charger      ★ same mall as ① (Jurong Point) · +0 min
 16:40 ● Arrive Changi · +13 min total
        [ Open in Google Maps ]
```
**Screen 3: Stop detail** (tap a stop or a pin): ranked list with name, detour, ETA, open-at-ETA badge, evidence badges ("OSM: diet:halal=yes" vs "name hint"), score breakdown, and an "Use this" button that pins it and replans.

**Screen 4: Hand-off**: summary of chosen stops in order, a warning if Google may drop waypoints (transit), and a button that opens
`https://www.google.com/maps/dir/?api=1&origin=…&destination=…&waypoints=a|b|c&travelmode=driving`.

## 9. Data-source limitations (be honest in the UI)

- **Halal:** OSM `diet:halal` coverage in Singapore is sparse. MUIS certification isn't in OSM and has no open API. Name and cuisine hints are weak evidence and are labelled as such. The app **never claims certification**.
- **Prayer rooms:** mall surau/musolla are rarely mapped in OSM, while mosques are well covered. Possible M4 enrichment: check whether data.gov.sg or OneMap Themes publish a mosque/prayer-room dataset with an open licence.
- **Opening hours:** many POIs have no `opening_hours` tag, so "unknown" will be common.
- **OSM freshness:** the data is as old as the last import. `/api/health` shows the import date.
- **Transit detours** are estimates (headway/2 wait). OneMap pt itineraries don't expose live headways.
- **Google Maps deep link:** waypoints are **not supported for transit** and are limited on mobile. For transit, the app offers one link per leg.
- **OneMap:** credentials must stay server-side. The token lasts about 3 days and is refreshed automatically. Endpoint paths and limits will be checked against the live API in M1 because the docs site is JS-rendered.
- **Geofabrik** has no Singapore-only extract. The import downloads `malaysia-singapore-brunei` and clips it to Singapore's boundary.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| OneMap API changes or downtime | Provider interface, ORS fallback for non-transit, recorded fixtures for tests |
| `pyosmium` wheels on Windows | Verify in M1; fallback: run the import in WSL/Docker or use a pure-Python PBF reader |
| Render cold start (~1 min after 15 min idle) | Frontend shows "waking server…" state; `/api/health` ping on page load |
| Render ephemeral disk | POI DB baked into the Docker image; route cache is disposable |
| Too many exact-detour calls | Top 3 only, cache, semaphore, token bucket |
| Rate limits on free LLMs | Rules backend is default; LLM is opt-in with fallback |
| Over-trusting halal or hours data | Evidence badges, "unknown" states, never filter on weak evidence |

## 11. Deployment (verified 2026-11-06, re-check at M7)

- **Frontend:** Vercel Hobby (static build).
- **Backend:** **Render Free web service (Docker)**. No card needed for the free tier, 750 instance-hours per month, sleeps after 15 min idle, about 1 min spin-up, ephemeral filesystem. If bandwidth runs out without a card on file, the service is suspended rather than billed.
- Ruled out: Hugging Face Docker Spaces (now need a paid plan), Koyeb (no free compute listed), PythonAnywhere free (no ASGI, outbound whitelist), Fly.io and Railway (card or trial).
- Backup: FastAPI Cloud Hobby (no card; 0.1 CPU, 500 MiB, 180 replica-hours per period).

## 12. Testing

- `pytest` unit tests for core: polyline time slicing, segment buffering, detour approximation, scoring, dedupe (same `osm_id` from node and way, or same name within 30 m), prayer placement, opening-hours evaluation, deep-link building, rule parser.
- Recorded OneMap fixtures in `backend/tests/fixtures/onemap/` for the three test routes. A `--record` flag refreshes them using real credentials.
  - NTU → Changi Airport (drive)
  - Jurong West → Sultan Mosque (transit)
  - NTU → Sentosa departing 12:30 (Zuhr + Asr during the trip)
- A fake `PlacesProvider` with a handful of POIs for deterministic planner tests.
- Frontend: Vitest for deep-link and timeline formatting; manual mobile checks.

## 13. Repo layout

```
/frontend          Vite React TS app
/backend
  app/{main.py, config.py, models.py, cache.py}
  app/core/        pure logic
  app/providers/   routing/ geocoding/ places/ llm/
  app/regions/     singapore.py
  scripts/import_osm.py
  tests/  eval/
  Dockerfile
/data              (gitignored) pbf + pois.sqlite
/docs              DESIGN.md, DECISIONS.md
.env.example
```

## 14. Milestones
0 Plan (this doc) → 1 Skeleton + import + route on map → 2 One stop end-to-end → 3 Multi-stop, open-at-ETA, combined → 4 Prayer awareness → 5 LLM backends + eval → 6 Deep link, PWA, polish → 7 Deploy + README. I'll stop after each milestone for your go-ahead.
