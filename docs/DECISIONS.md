# Design decisions

Short records of trade-offs. Newest at the bottom. Format: context → decision → consequence.

## D1 — Backend host: Render Free (2026-11-06)
- **Context:** must be $0 with no card. HF Docker Spaces now require a paid plan. Koyeb lists no free compute. PythonAnywhere free has no ASGI and whitelists outbound hosts. Fly.io and Railway need a card or trial.
- **Decision:** Render Free web service (Docker). Backup: FastAPI Cloud Hobby.
- **Consequence:** about 1 min cold start after 15 min idle, and an ephemeral disk. The POI DB ships inside the image, the route cache is disposable, and the frontend shows a "waking server" state.

## D2 — OSM data imported once into SQLite + R*Tree (2026-11-06)
- **Context:** runtime Overpass queries are slow, rate-limited and unfriendly to a public service.
- **Decision:** a re-runnable `scripts/import_osm.py` (Geofabrik `malaysia-singapore-brunei` → clip to SG → POIs → SQLite with R*Tree).
- **Consequence:** data is only as fresh as the last import, shown in `/api/health`. The code needs no extra spatial DB server.

## D3 — Parsers output a category enum, not raw OSM tags (2026-11-06)
- **Context:** an LLM can produce invalid or invented tags, and that would make backend comparisons unfair.
- **Decision:** every parser maps text → fixed `category` + dietary + time window. A deterministic dictionary maps category → OSM filters.
- **Consequence:** adding a new kind of place means a dictionary entry, not a prompt change. The eval compares like with like.

## D4 — Rank by detour minutes; exact routing only for the top 3 (2026-11-06)
- **Context:** an exact detour costs about 2 routing calls per candidate, and OneMap is rate-limited.
- **Decision:** cheap geometric estimate (`2 × offset × circuity / speed`) for all candidates. Exact `prev→place→next − prev→next` for the top 3 per stop, cached.
- **Consequence:** candidates ranked 4th and lower may be slightly misordered, which is acceptable. Each candidate carries a `detour_exact` flag.

## D5 — Transit detours = hop off, walk, re-board (2026-11-06)
- **Context:** "detour" is ambiguous for public transport.
- **Decision:** only stops and stations where the itinerary halts are eligible. Detour = walk there and back + expected wait (headway/2). Exact check via OneMap pt for the top 3.
- **Consequence:** wait times are estimates. Google deep links can't carry transit waypoints, so the app offers per-leg links.

## D6 — Added `dwell_min` to StopRequest (2026-11-06)
- **Context:** the spec's model has no stop duration, so ETAs after a 45-min lunch would be wrong.
- **Decision:** a per-category default dwell (meal 45, prayer 20, shop 15), editable.
- **Consequence:** later ETAs, prayer placement and open-at-ETA checks all account for time spent at earlier stops.

## D7 — Greedy multi-stop cascade, not global optimisation (2026-11-06)
- **Context:** choosing the jointly best set of stops is a combinatorial search.
- **Decision:** process stops in target-time order, pick the best one, shift the clock, continue. Combined stops are scored by actual minutes saved.
- **Consequence:** simple and explainable, and occasionally sub-optimal. The user can pin alternatives and replan.

## D8 — Prayer method: MUIS + Shafi'i Asr default, Hanafi toggle (2026-11-06)
- **Decision:** `adhanpy` with `CalculationMethod.SINGAPORE`. Asr madhab is a user preference. Times are computed at the origin because Singapore varies by only about 2 minutes; per-position computation is kept for other regions.

## D9 — Weak evidence is labelled, never hidden or promoted (2026-11-06)
- **Context:** halal tags, prayer rooms and opening hours are sparse in OSM.
- **Decision:** evidence badges ("OSM diet:halal=yes" vs "name hint"), a small penalty for weak evidence, `unknown` hours shown in grey. Places with **no** evidence for a required dietary constraint are excluded.
- **Consequence:** fewer but more trustworthy results. The app never claims MUIS certification.

## D10 — Local equirectangular projection instead of pyproj (2026-11-06)
- **Decision:** project lat/lng to metres around the region's centre for buffer and offset math.
- **Consequence:** under 0.1% error across Singapore and one fewer heavy dependency. Larger regions would need a per-region origin or a real CRS.
