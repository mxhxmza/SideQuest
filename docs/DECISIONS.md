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

## D11 — Keyless fallbacks so the app runs with zero credentials (2026-11-26)
- **Context:** OneMap needs an account (and since 2024 its Search API also needs a token). Without credentials the app could not route or geocode at all.
- **Decision:** routing chain `onemap → ors → osrm (FOSSGIS routing.openstreetmap.de: drive/walk/cycle) → osrm_demo (router.project-osrm.org: drive)`; geocoding chain `onemap → photon (komoot, SG bbox) → local POI names`. Each is skipped when unconfigured; all are configurable/disable-able in `.env`. Calls are cached and rate-limited (token bucket), and exact-detour checks use duration-only requests.
- **Consequence:** works out of the box for drive/walk/cycle. **Transit still requires OneMap** (no keyless SG transit router) and the UI says so. Community servers have usage policies and no SLA — fine for a hobby project, not for heavy traffic; OneMap stays the primary.

## D12 — Two extra scoring terms (2026-11-26)
- **Context:** in live testing, many candidates sat inside the ±tolerance window with near-equal detours, so the winner was arbitrary; and a stop chosen later in the greedy pass (e.g. an "any time" charger) could push an earlier timed stop (lunch) out of its window.
- **Decision:** `off_target = 0.1 · min(|eta − target|, tolerance)` (tie-breaker, max 2 min) and `pushes_other_stops = 0.5 · minutes by which this choice pushes already-chosen timed stops past their window` (same weight as `outside_window`). Both appear in `score_breakdown`. If a stop still ends up outside its window, the plan carries a warning. When a requested time lies outside the trip, the search is clamped to the first/last quarter of the route (10–20 min), not the whole window.
- **Consequence:** rankings stay explainable minutes; greedy cascade (D7) is less likely to break earlier choices.

## D13 — Exact detours via one matrix request when available (2026-11-26)
- **Context:** exact detours cost ~3 routing calls per candidate; through rate-limited community servers a 3-stop plan took ~25 s, and real detours were often larger than the geometric estimate, so unverified candidates floated to the top after re-ranking.
- **Decision:** if the routing chain has a matrix-capable provider (OSRM `table`), all exact detours for a stop come from **one** request, so up to 8 candidates are verified; the planner re-verifies (≤4 rounds) until the top choice has an exact detour. Pairwise calls (thread pool of 4, cached) remain for providers without a matrix (OneMap, ORS) and keep D4's top-3 limit. The FOSSGIS table service is throttled (~10 s/request), so it is not used; driving matrices go to the OSRM demo server.
- **Consequence:** a fresh 3-stop drive plan takes ~3 s (cached replans <1.5 s). Driving routes and matrices may come from two OSRM instances with the same OSM car profile.

## D14 — Shrines are not prayer places (2026-11-26)
- **Context:** OSM tags some keramat (shrines/tombs) as `amenity=place_of_worship + religion=muslim`; one was suggested as a mosque.
- **Decision:** for prayer categories, exclude places with a `historic=*` tag or names containing keramat/makam/tomb/shrine/cemetery/kubur.

## D15 — OneMap in practice: login back-off, provider-aware caches, re-ranked search (2026-11-26)
- **Context:** first run with real credentials. (1) OneMap's API rejects passwords under 12 characters with a misleading "should be between 8 and 60 characters"; every routing call then re-sent the bad login. (2) Routes and searches cached while OneMap was unavailable kept being served after it worked. (3) OneMap search often ranks a partial match first ("Jurong Point" → a clinic). (4) With OneMap primary for driving, exact detours went pairwise through OneMap (~90 calls, 16 s).
- **Decision:** (1) after a rejected login, OneMap is skipped for 15 min (no network calls); its reason shows in `/api/health` and in transit errors. (2) Route/duration/geocode cache keys include the provider that would answer now. (3) Geocoding re-ranks by name match (exact > starts-with > contains, provider order kept within a tier); if the first provider has no exact match, fallbacks are merged in. (4) Exact driving detours use the OSRM matrix even when OneMap draws the main route; each detour (prev→place→next − prev→next) is computed within one provider, so it is self-consistent. Walk/cycle/transit hop-off walks stay pairwise (top 3) through OneMap.
- **Consequence:** a 3-stop OneMap drive plan takes ~3 s fresh (~1.4 s cached), transit ~2–10 s depending on cache. Driving detours and the main route can come from different engines (OSRM vs OneMap); the "About this data" panel names the route provider.

## D16 — Dietary fallback: show unverified options rather than nothing (2026-11-26)
- **Context:** D9 excluded places with no evidence for a required dietary constraint. Only 6 of 214 ice-cream/dessert places in SG OSM carry `diet:halal`, so "halal ice cream along the way" usually returned nothing.
- **Decision:** exclusion stays the rule. Only when *no* candidate along the stretch has any evidence, the planner shows unverified candidates, each badged "no halal evidence in OSM — check on site" (+5 weak-evidence penalty), and the stop carries a warning. Places tagged `diet:halal=no` are never shown. Evidenced options, when they exist, are the only ones listed.
- **Consequence:** users get something to act on, never a certification claim. Supersedes the "excluded" part of D9 for the empty case only.

## D17 — Requests the lexicon doesn't know become name searches (2026-11-26)
- **Context:** "some halal shop to buy ice cream" was merged into the previous clause as a "fragment" and silently lost.
- **Decision:** added an `ice_cream` category. Fragments are merged only when they are pure modifiers (time/dietary/filler words). A clause with real content but no category becomes a `keyword` stop: a place-name search on its content words ("buy durian" → names containing "durian"), labelled as a name match (weak evidence). Clauses with no content are returned in `ParseResponse.unrecognized` and shown to the user. LLM parsers may emit `keyword` with `keywords`, still from the fixed enum (D3 holds: no invented tags).
- **Consequence:** nothing the user asks for disappears silently.

## D18 — Prompt-first UI; Asr method no longer a user option (2026-11-26)
- **Decision:** the UI is start → destination → time → mode → free-text prompt, parsed live as the user types (chips appear as it understands). The Shafi'i/Hanafi selector was removed at the user's request; the UI always uses MUIS (Shafi'i). The API still accepts `prefs.asr_method` (D8) for other clients.

## D19 — Time windows apply to arriving at the place, not to leaving the route (2026-11-26)
- **Context:** "mosque to pray Asr anytime until 6pm" by transit from Jurong West to one-north returned "no mosque along the way". Asr (16:17) began between Clementi and Dover, so only stations from Dover on were searched — none within 800 m of a mosque. Masjid Darussalam (Clementi) and Masjid Al-Mukminin (Jurong East) were reachable *after* 16:17 by getting off a station earlier, but were excluded because the train left those stations before 16:17. "until 6pm" was also ignored (window stayed Asr + 60 min), and "halal" was dropped from "halal … cake" (bakery wasn't a food category).
- **Decision:** (1) A timed stop's search starts one *lead* earlier on the route: the one-way time to a place at the buffer's edge (`buffer · circuity / speed`, walking for transit: ~13 min transit/walk, ~5 min drive, ~6 min cycle). (2) Prayer windows (at/after) have a hard start: a place reached before the prayer begins means waiting there; the wait is real added time (`wait_min` on the candidate, a `wait` score term, counted in `added_min` and the trip clock) and is recomputed in route order once all stops are placed, so an earlier stop that delays you shortens it. Anywhere in [start, end] is in the window; earlier is a 0.1/min tie-breaker. (3) `TimeWindow.until` ("HH:MM") sets a prayer window's end, capped at the prayer's end time; the rules parser reads "until / till / by / before <time>", LLM parsers emit it. (4) Bakery is a food category, so dietary constraints apply. (5) D16's fallback is decided after the distance check: an evidenced place inside the search bbox but out of reach no longer hides unverified places next to the route (two halal-tagged bakeries ~3 km from every station did exactly that).
- **Consequence:** the example now offers Masjid Darussalam (hop off Clementi, arrive 16:39) and Masjid Al-Mukminin (Jurong East), plus unverified bakeries. Clock-time windows also search one lead earlier; early arrivals there are still scored by `outside_window`, not waited for. When the whole window lies after arrival (e.g. a short drive ending before Asr) the old clamp still applies: mosques near the end, with a warning, without counting a wait.
