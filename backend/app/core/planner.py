"""Trip planner: route → timeline → per-stop candidates → greedy cascade (DESIGN §5).

Providers are injected; this module never imports a concrete provider.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np

from app.core import deeplink, hours, prayer
from app.core import tags as T
from app.core.detour import (estimate_detour_min, exact_detour_min, exact_transit_detour_min,
                             neighbour_distance_m, transit_detour_min)
from app.core.geo import Projection
from app.core.scoring import category_evidence, dedupe, dietary_evidence, score
from app.core.segments import Clock, Window, resolve_window, window_to_route_range
from app.core.timeline import Timeline
from app.models import (EtaWindow, Evidence, LegLink, OsmFilter, ParentRef, Place, PlaceCandidate, Point,
                        PrayerOnRoute, RouteLegOut, RouteOut, StopPlan, StopRequest, TimelineRow, TripPlan,
                        TripRequest)
from app.providers.base import PlacesProvider, ProviderError, RoutingProvider
from app.regions.base import Region

log = logging.getLogger(__name__)

TOP_N = 5          # candidates returned per stop
EXACT_N = 3        # exact detour for the top 3 (D4) with pairwise routing
EXACT_N_MATRIX = 8 # one matrix request covers more candidates for free
COMBINE_SCAN = 15  # candidates examined for combinations
HOURS_EVAL_N = 80  # opening hours evaluated for the best-N by detour
MAX_STOPS = 8


def normalize_stop(s: StopRequest) -> StopRequest:
    """Fill deterministic fields from the category dictionary (D3)."""
    cat = T.get(s.category)
    s = s.model_copy(deep=True)
    s.osm_filters = [OsmFilter(tags={k: list(v) for k, v in f.items()}) for f in cat.filters]
    if s.category == "keyword":
        # name search: keywords come from the request, cleaned and bounded
        kws = []
        for k in s.name_keywords:
            k = " ".join(k.lower().split())[:40]
            if len(k) >= 3 and k not in kws:
                kws.append(k)
        s.name_keywords = kws[:4]
        if not s.label and kws:
            s.label = kws[0].title()
    else:
        s.name_keywords = list(cat.name_keywords)
    if s.dwell_min is None:
        s.dwell_min = cat.dwell_min
    s.label = s.label or cat.label
    s.icon = s.icon or cat.icon
    if s.constraints.dietary and cat.kind not in T.DIETARY_KINDS:
        # dietary only makes sense for food; ignore elsewhere rather than exclude everything
        s.constraints.dietary = []
    return s


@dataclass
class _Raw:
    place: Place
    offset_m: float
    along_t: float
    along_m: float
    detour: float
    hop_off: Optional[str] = None
    hop_xy: Optional[tuple[float, float]] = None  # lat,lng of hop-off halt (transit)
    wait_min: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    weak_diet: bool = False
    weak_cat: bool = False
    unverified: bool = False  # dietary fallback: no evidence at all (D16)


class Planner:
    def __init__(self, routing: RoutingProvider, places: PlacesProvider, region: Region,
                 exact_workers: int = 4, exact: bool = True):
        self.routing = routing
        self.places = places
        self.region = region
        self.tz = ZoneInfo(region.timezone)
        self.proj = Projection(*region.center)
        self.exact_workers = exact_workers
        self.exact = exact
        self._children_cache: dict[int, list[Place]] = {}
        # (along_s, eta, window_end) of timed stops chosen so far — for the push penalty
        self._timed_chosen: list[tuple[float, datetime, datetime]] = []

    def _push_overflow(self, along_s: float, delay_min: float) -> float:
        """Minutes by which inserting a stop here would push already-chosen timed
        stops (later on the route) past the end of their windows."""
        total = 0.0
        for a, eta, end in self._timed_chosen:
            if a > along_s + 1:
                total += max(0.0, (eta + timedelta(minutes=delay_min) - end).total_seconds() / 60
                             - max(0.0, (eta - end).total_seconds() / 60))
        return total

    # ------------------------------------------------------------ helpers --
    def _route_s(self, a, b, mode, when) -> float:
        fn = getattr(self.routing, "duration_s", None)
        return fn(a, b, mode, when) if fn else self.routing.route(a, b, mode, when).duration_s

    def _lead_s(self, mode: str) -> float:
        """One-way time from the route to a place at the buffer's edge (walking, for
        transit hop-offs): how far before a window opens the search must start."""
        speed = self.region.mode_speed_kmh.get("walk" if mode == "transit" else mode, 30.0)
        return self.region.buffer_m.get(mode, 1000.0) * self.region.circuity / (speed / 3.6)

    @staticmethod
    def _fit(eta: datetime, win: Window) -> tuple[Optional[float], float, float]:
        """(minutes off target, tolerance, minutes waiting) for arriving at `eta`."""
        if win.target is None:
            return None, 0.0, 0.0
        if win.hard_start:
            # served at max(eta, start): early means waiting there; the whole
            # [start, end] is in the window, earlier preferred (tie-breaker)
            wait = max(0.0, (win.start - eta).total_seconds() / 60)
            off = max(0.0, (eta - win.start).total_seconds() / 60)
            return off, (win.end - win.start).total_seconds() / 60, wait
        return (eta - win.target).total_seconds() / 60, (win.end - win.start).total_seconds() / 120, 0.0

    def _children(self, pid: int) -> list[Place]:
        if pid not in self._children_cache:
            self._children_cache[pid] = self.places.children(pid)
        return self._children_cache[pid]

    def _prayer_lookup(self, origin: Point, asr: str, method: str):
        def lookup(name: str, at: datetime):
            w = prayer.next_or_current(origin.lat, origin.lng, name, at, asr, method, self.region.timezone)
            return w.start, w.end
        return lookup

    # --------------------------------------------------------- candidates --
    def _raw_candidates(self, stop: StopRequest, tl: Timeline, t0: float, t1: float,
                        mode: str) -> list[_Raw]:
        cat = T.get(stop.category)
        buf = self.region.buffer_m.get(mode, 1000.0)
        circ = self.region.circuity
        walk_kmh = self.region.mode_speed_kmh.get("walk", 4.8)

        halts = []
        walk_ranges: list[tuple[float, float]] = []
        if mode == "transit":
            halts = [h for h in tl.halts if t0 <= h.t <= t1]
            walk_ranges = [(max(a, t0), min(b, t1)) for a, b in tl.walk_ranges() if b >= t0 and a <= t1]
            pts_lat = [h.lat for h in halts]
            pts_lng = [h.lng for h in halts]
            for a, b in walk_ranges:
                bb = tl.bbox_latlng(a, b)
                pts_lat += [bb[0], bb[2]]
                pts_lng += [bb[1], bb[3]]
            if not pts_lat:
                return []
            bbox = (min(pts_lat), min(pts_lng), max(pts_lat), max(pts_lng))
        else:
            bbox = tl.bbox_latlng(t0, t1)
        bbox = self.proj.expand_bbox(*bbox, buf)
        places = self.places.query(bbox, [dict((k, tuple(v)) for k, v in f.tags.items()) for f in stop.osm_filters],
                                   tuple(stop.name_keywords))
        if not places:
            return []

        # category + dietary evidence first (cheap; excludes places with no dietary evidence)
        kept: list[tuple[Place, list[Evidence], bool, bool]] = []
        unverified: list[tuple[Place, list[Evidence], bool, bool]] = []
        diet = list(stop.constraints.dietary)
        for p in places:
            tags = dict(p.tags)
            if p.name:
                tags.setdefault("name", p.name)
            ok, cev = category_evidence(cat, tags, stop.name_keywords)
            if not ok:
                continue
            weak_cat = all(e.strength == "weak" for e in cev)
            dok, dev, weak = dietary_evidence(tags, diet)
            if not dok:
                if not dev:  # no evidence either way (an explicit "no" is never shown)
                    note = Evidence(text=f"no {'/'.join(diet)} evidence in OSM — check on site", strength="weak")
                    unverified.append((p, cev + [note], True, weak_cat))
                continue
            kept.append((p, cev + dev, weak, weak_cat))

        def on_route(items: list[tuple[Place, list[Evidence], bool, bool]], fallback: bool) -> list[_Raw]:
            """Places within reach of the stretch, with their detour estimates."""
            items = dedupe(items, key_latlng=lambda k: (k[0].lat, k[0].lng), key_name=lambda k: k[0].name,
                           key_osm=lambda k: k[0].osm_id, key_tags=lambda k: k[0].tags)
            xy = [self.proj.to_xy(k[0].lat, k[0].lng) for k in items]
            px = np.array([p[0] for p in xy])
            py = np.array([p[1] for p in xy])
            out: list[_Raw] = []
            if mode != "transit":
                speed = self.region.mode_speed_kmh.get(mode, 30.0)
                near = tl.nearest_many(px, py, t0, t1)
                for (p, ev, weak, weak_cat), n in zip(items, near):
                    if n.dist_m > buf:
                        continue
                    out.append(_Raw(p, n.dist_m, n.along_t, n.along_m,
                                    estimate_detour_min(n.dist_m, speed, circ), evidence=ev,
                                    weak_diet=weak, weak_cat=weak_cat, unverified=fallback))
                return out

            # transit: hop off at a halt (walk + wait) or divert while on a walking leg
            hx = np.array([h.x for h in halts]) if halts else None
            hy = np.array([h.y for h in halts]) if halts else None
            walk_near = []
            if walk_ranges:
                per_range = [tl.nearest_many(px, py, a, b) for a, b in walk_ranges]
                walk_near = [min((r[i] for r in per_range), key=lambda n: n.dist_m) for i in range(len(items))]
            for i, (p, ev, weak, weak_cat) in enumerate(items):
                best: Optional[_Raw] = None
                if halts:
                    d = np.hypot(hx - px[i], hy - py[i])
                    j = int(np.argmin(d))
                    if d[j] <= buf:
                        h = halts[j]
                        wait = self.region.transit_wait_min.get(h.mode,
                                                                self.region.transit_wait_min.get("default", 4.0))
                        best = _Raw(p, float(d[j]), h.t, tl.distance_at(h.t),
                                    transit_detour_min(float(d[j]), walk_kmh, wait, circ),
                                    hop_off=h.name or None, hop_xy=(h.lat, h.lng), wait_min=wait,
                                    evidence=ev, weak_diet=weak, weak_cat=weak_cat)
                if walk_near:
                    n = walk_near[i]
                    if n.dist_m <= buf:
                        det = estimate_detour_min(n.dist_m, walk_kmh, circ)
                        if best is None or det < best.detour:
                            best = _Raw(p, n.dist_m, n.along_t, n.along_m, det, evidence=ev,
                                        weak_diet=weak, weak_cat=weak_cat)
                if best:
                    best.unverified = fallback
                    out.append(best)
            return out

        out = on_route(kept, False) if kept else []
        if not out and unverified:
            # D16: nothing within reach of this stretch has dietary evidence — show unverified
            # options, clearly labelled, instead of an empty result. Decided after the distance
            # check: an evidenced place kilometres off the route must not hide the nearby ones.
            out = on_route(unverified, True)
        return out

    def _to_candidate(self, stop: StopRequest, r: _Raw, clock: Clock, win: Window,
                      eval_hours: bool = True) -> PlaceCandidate:
        eta = clock.at(r.along_t) + timedelta(minutes=r.detour / 2)
        open_state = hours.open_at(r.place.tags.get("opening_hours"), eta, self.region.timezone) \
            if eval_hours else "unknown"
        off, tol, wait = self._fit(eta, win)
        push = self._push_overflow(r.along_t, r.detour + wait + (stop.dwell_min or 0))
        s, b = score(r.detour, open_state, stop.constraints.open_at_eta, off, tol,
                     bool(r.place.name), r.weak_diet, r.weak_cat, push_overflow_min=push, wait_min=wait)
        parent = None
        if r.place.parent_id:
            pp = self.places.get(r.place.parent_id)
            if pp:
                parent = ParentRef(id=pp.id, osm_id=pp.osm_id, name=pp.name)
        return PlaceCandidate(
            osm_id=r.place.osm_id, name=r.place.name, lat=r.place.lat, lng=r.place.lng,
            tags=r.place.tags, open_at_eta=open_state, detour_min=round(r.detour, 1), detour_exact=False,
            eta=eta, score=s, score_breakdown=b, matched_stop_ids=[stop.id], evidence=r.evidence,
            offset_m=round(r.offset_m), along_s=round(r.along_t, 1), parent=parent, hop_off=r.hop_off,
            wait_min=round(wait, 1))

    def _exact_matrix(self, items: list[tuple[PlaceCandidate, _Raw]], tl: Timeline, mode: str) -> Optional[list]:
        """All exact detours for a stop from ONE matrix request (when the provider has one)."""
        fn = getattr(self.routing, "matrix_s", None)
        if fn is None:
            return None
        legs = []  # (kind, a, place, b, wait)
        for c, r in items:
            place = (c.lat, c.lng)
            if mode == "transit" and r.hop_xy is not None:
                legs.append(("hop", r.hop_xy, place, r.hop_xy, r.wait_min))
            else:
                d = neighbour_distance_m(r.offset_m)
                prev = tl.position_at_distance(max(0.0, r.along_m - d))
                nxt = tl.position_at_distance(min(tl.length, r.along_m + d))
                legs.append(("via", prev, place, nxt, 0.0))
        pts: list = []
        index: dict = {}
        for _, a, p, b, _ in legs:
            for q in (a, p, b):
                k = (round(q[0], 6), round(q[1], 6))
                if k not in index:
                    index[k] = len(pts)
                    pts.append(q)
        ix = lambda q: index[(round(q[0], 6), round(q[1], 6))]  # noqa: E731
        try:
            m = fn(pts, "walk" if mode == "transit" else mode)
        except Exception as e:  # NotImplementedError / provider failure → pairwise
            log.info("matrix unavailable (%s); using pairwise exact detours", e)
            return None
        out = []
        for kind, a, p, b, wait in legs:
            ia, ip, ib = ix(a), ix(p), ix(b)
            if kind == "hop":
                v = (m[ia][ip] + m[ip][ia]) / 60 + wait
            else:
                v = (m[ia][ip] + m[ip][ib] - m[ia][ib]) / 60
            out.append(None if v != v else max(0.0, v))  # NaN → unroutable
        return out

    def _exact(self, items: list[tuple[PlaceCandidate, _Raw]], tl: Timeline, mode: str, clock: Clock) -> None:
        if not self.exact or not items:
            return
        results = self._exact_matrix(items, tl, mode)
        if results is not None:
            self._apply_exact(items, results)
            return

        def work(pair):
            c, r = pair
            when = clock.at(r.along_t)
            try:
                if mode == "transit":
                    if r.hop_xy is None:  # diverting from a walking leg
                        d = neighbour_distance_m(r.offset_m)
                        prev = tl.position_at_distance(max(0.0, r.along_m - d))
                        nxt = tl.position_at_distance(min(tl.length, r.along_m + d))
                        return exact_detour_min(self._route_s, prev, (c.lat, c.lng), nxt, "walk", when)
                    return exact_transit_detour_min(self._route_s, r.hop_xy, (c.lat, c.lng), r.wait_min, when)
                d = neighbour_distance_m(r.offset_m)
                prev = tl.position_at_distance(max(0.0, r.along_m - d))
                nxt = tl.position_at_distance(min(tl.length, r.along_m + d))
                return exact_detour_min(self._route_s, prev, (c.lat, c.lng), nxt, mode, when)
            except Exception as e:  # keep the estimate (detour_exact=False)
                log.info("exact detour failed for %s: %s", c.osm_id, e)
                return None

        with ThreadPoolExecutor(max_workers=self.exact_workers) as ex:
            results = list(ex.map(work, items))
        self._apply_exact(items, results)

    @staticmethod
    def _apply_exact(items, results) -> None:
        for (c, r), v in zip(items, results):
            if v is None:
                continue
            r.detour = v
            c.detour_min = round(v, 1)
            c.detour_exact = True

    def _rescore(self, stop: StopRequest, c: PlaceCandidate, r: Optional[_Raw], clock: Clock, win: Window,
                 bonus: float = 0.0) -> None:
        if r is not None:
            c.eta = clock.at(r.along_t) + timedelta(minutes=c.detour_min / 2)
            c.open_at_eta = hours.open_at(c.tags.get("opening_hours"), c.eta, self.region.timezone)
        off, tol, wait = self._fit(c.eta, win)
        c.wait_min = round(wait, 1)
        weak_diet = "weak_dietary_evidence" in c.score_breakdown
        weak_cat = "name_hint_only" in c.score_breakdown
        push = self._push_overflow(c.along_s, c.detour_min + wait + (stop.dwell_min or 0))
        c.score, c.score_breakdown = score(c.detour_min, c.open_at_eta, stop.constraints.open_at_eta, off, tol,
                                           bool(c.name), weak_diet, weak_cat, bonus, push_overflow_min=push,
                                           wait_min=wait)

    # ------------------------------------------------------- combinations --
    def _covers(self, c: PlaceCandidate, place: Place, other: StopRequest, other_win: Window,
                eta: datetime) -> Optional[tuple[str, Place, list[Evidence]]]:
        """Can `place` (chosen for one stop) also serve `other`? Same POI, or a
        matching POI inside the same container (mall)."""
        timed = other.time_window.type != "any"
        if timed and not (other_win.start - timedelta(minutes=5) <= eta <= other_win.end + timedelta(minutes=5)):
            return None
        cat = T.get(other.category)

        def match(p: Place):
            tags = dict(p.tags)
            if p.name:
                tags.setdefault("name", p.name)
            ok, cev = category_evidence(cat, tags, other.name_keywords)
            if not ok:
                return None
            dok, dev, _ = dietary_evidence(tags, list(other.constraints.dietary))
            if not dok:
                return None
            return cev + dev

        ev = match(place)
        if ev is not None:
            return "same_poi", place, ev
        container_id = place.id if place.is_container else place.parent_id
        if not container_id:
            return None
        best = None
        for sib in self._children(container_id):
            if sib.id == place.id:
                continue
            ev = match(sib)
            if ev is None:
                continue
            strong = sum(e.strength == "strong" for e in ev)
            key = (strong, bool(sib.name))
            if best is None or key > best[0]:
                best = (key, sib, ev)
        if best:
            return "container", best[1], best[2]
        return None

    # --------------------------------------------------------------- plan --
    def plan(self, req: TripRequest) -> TripPlan:
        warnings: list[str] = []
        self._timed_chosen = []
        depart = req.departure_time.astimezone(self.tz)
        mode = req.mode
        origin, dest = req.origin, req.destination
        for p, label in ((origin, "Origin"), (dest, "Destination")):
            a, b, c, d = self.region.bbox
            if not (a <= p.lat <= c and b <= p.lng <= d):
                raise ProviderError(f"{label} is outside {self.region.name}")
        route = self.routing.route((origin.lat, origin.lng), (dest.lat, dest.lng), mode, depart)
        tl = Timeline(route, self.proj)
        stops = [normalize_stop(s) for s in req.stops[:MAX_STOPS]]
        if len(req.stops) > MAX_STOPS:
            warnings.append(f"Only the first {MAX_STOPS} stops are planned")

        lookup = self._prayer_lookup(origin, req.prefs.asr_method, req.prefs.prayer_method)
        base_clock = Clock(depart)
        base_arrival = base_clock.at(tl.duration)

        def window_for(s: StopRequest, clock: Clock) -> Window:
            arrival = clock.at(tl.duration)
            try:
                return resolve_window(s, depart, arrival, lookup)
            except ValueError as e:
                warnings.append(f"{s.label}: {e}; searching the whole route")
                return Window(depart, arrival, None)

        # order by target time; 'any' last so it can be combined into timed stops
        def order_key(s: StopRequest):
            w = window_for(s, base_clock)
            return (0, w.target) if w.target is not None else (1, base_arrival)

        ordered = sorted(stops, key=order_key)
        lead = self._lead_s(mode)

        # standalone best detour per stop on the unshifted clock (for combine_bonus, §5.7)
        base_best: dict[str, float] = {}
        for s in ordered:
            w = window_for(s, base_clock)
            t0, t1, _ = window_to_route_range(w, base_clock, tl.duration, lead)
            raws = self._raw_candidates(s, tl, t0, t1, mode)
            base_best[s.id] = min((r.detour for r in raws), default=0.0)

        clock = Clock(depart)
        plans: dict[str, StopPlan] = {}
        covered: dict[str, tuple[str, PlaceCandidate]] = {}
        chosen_raw: dict[str, Optional[_Raw]] = {}
        wins: dict[str, Window] = {}

        for idx, s in enumerate(ordered):
            win = window_for(s, clock)
            t0, t1, wwarn = window_to_route_range(win, clock, tl.duration, lead)
            swarn = list(win.warnings) + wwarn
            if wwarn:  # clamped: rank by detour only within the clamped stretch
                win = Window(clock.at(t0), clock.at(t1), None, win.prayer, win.warnings)
            wins[s.id] = win
            raws = self._raw_candidates(s, tl, t0, t1, mode)
            raws.sort(key=lambda r: r.detour)
            if raws and all(r.unverified for r in raws):
                swarn.append(f"No {'/'.join(s.constraints.dietary)}-tagged {s.label.lower()} places along this part of "
                             "the route — these options are unverified, check on site")
            cands = [(self._to_candidate(s, r, clock, win, eval_hours=i < HOURS_EVAL_N), r)
                     for i, r in enumerate(raws)]
            cands.sort(key=lambda cr: cr[0].score)
            pin = req.pinned.get(s.id)

            if s.id in covered and not pin:
                by, cc = covered[s.id]
                others = [c for c, _ in cands if c.osm_id != cc.osm_id][:TOP_N - 1]
                plans[s.id] = StopPlan(request=s, eta_window=EtaWindow(start=win.start, end=win.end, target=win.target),
                                       candidates=[cc] + others, chosen=cc, covered_by=by,
                                       added_min=0.0, warnings=swarn)
                chosen_raw[s.id] = None
                cc.along_s = clock.free_slot(cc.along_s)  # after the stop that covers it
                clock.add(cc.along_s, (s.dwell_min or 0) * 60)
                continue

            # combinations with later, not-yet-covered stops
            later = [o for o in ordered[idx + 1:] if o.id not in covered and o.id not in req.pinned]
            combo_info: dict[str, list[tuple[StopRequest, str, Place, list[Evidence]]]] = {}
            if later and not pin:
                later_wins = {o.id: window_for(o, clock) for o in later}
                for c, r in cands[:COMBINE_SCAN]:
                    hits = []
                    for o in later:
                        eta_o = c.eta + timedelta(minutes=c.wait_min + (s.dwell_min or 0))
                        cov = self._covers(c, r.place, o, later_wins[o.id], eta_o)
                        if cov:
                            hits.append((o, *cov))
                    if hits:
                        combo_info[c.osm_id] = hits
                        saved = base_best.get(s.id, 0) + sum(base_best.get(o.id, 0) for o, *_ in hits) - c.detour_min
                        c.kind = "same_poi" if all(h[1] == "same_poi" for h in hits) else "container"
                        c.matched_stop_ids = [s.id] + [o.id for o, *_ in hits]
                        names = ", ".join(f"{o.label}" + (f" ({p.name})" if p.name and kind == "container" else "")
                                          for o, kind, p, _ in hits)
                        where = (c.parent.name if c.parent and c.kind == "container" else c.name) or "here"
                        c.combined_note = f"Also covers {names} at {where}"
                        self._rescore(s, c, None, clock, win, bonus=max(0.0, saved))
                cands.sort(key=lambda cr: cr[0].score)

            # exact detour for the top few, then re-rank
            has_matrix = getattr(self.routing, "has_matrix", None)
            matrix_mode = "walk" if mode == "transit" else mode
            n_exact = EXACT_N_MATRIX if has_matrix and has_matrix(matrix_mode) else EXACT_N
            top = cands[:n_exact]
            self._exact(top, tl, mode, clock)
            for c, r in top:
                bonus = -c.score_breakdown.get("combine_bonus", 0.0)
                if c.osm_id in combo_info:
                    hits = combo_info[c.osm_id]
                    bonus = max(0.0, base_best.get(s.id, 0) + sum(base_best.get(o.id, 0) for o, *_ in hits) - c.detour_min)
                self._rescore(s, c, r, clock, win, bonus)
            cands.sort(key=lambda cr: cr[0].score)
            # estimates tend to be optimistic: if an unverified option rose to the top,
            # verify the next few too (bounded) so the winner always has an exact detour
            for _ in range(4):
                pending = [cr for cr in cands[:n_exact] if not cr[0].detour_exact]
                if not pending or cands[0][0].detour_exact:
                    break
                self._exact(pending, tl, mode, clock)
                for c, r in pending:
                    bonus = -c.score_breakdown.get("combine_bonus", 0.0)
                    if c.osm_id in combo_info:
                        hits = combo_info[c.osm_id]
                        bonus = max(0.0, base_best.get(s.id, 0) + sum(base_best.get(o.id, 0) for o, *_ in hits)
                                    - c.detour_min)
                    self._rescore(s, c, r, clock, win, bonus)
                cands.sort(key=lambda cr: cr[0].score)

            chosen: Optional[PlaceCandidate] = None
            chosen_r: Optional[_Raw] = None
            if pin:
                found = next(((c, r) for c, r in cands if c.osm_id == pin), None)
                if found is None:
                    found = self._pinned_outside(s, pin, tl, mode, clock, win)
                    if found is None:
                        swarn.append(f"Pinned place {pin} not found; using the best option")
                    else:
                        swarn.append("Pinned place is outside the requested time window")
                        cands.append(found)
                if found is not None:
                    chosen, chosen_r = found
                    if found[1] is not None and found[0].detour_exact is False:
                        self._exact([found], tl, mode, clock)
                        self._rescore(s, found[0], found[1], clock, win)
            if chosen is None and cands:
                chosen, chosen_r = cands[0]

            top_list = [c for c, _ in cands[:TOP_N]]
            if chosen is not None and chosen not in top_list:
                top_list = [chosen] + top_list[:TOP_N - 1]
            if not cands:
                swarn.append("No matching places found along this part of the route")

            added = 0.0
            if chosen is not None:
                # a stop at the same route point as an earlier choice goes after it
                chosen.along_s = clock.free_slot(chosen.along_s)
                if s.time_window.type != "any":
                    self._timed_chosen.append((chosen.along_s, chosen.eta, win.end))
                # waiting for a prayer time to start delays the trip like a detour does
                added = chosen.detour_min + chosen.wait_min
                clock.add(chosen.along_s, (added + (s.dwell_min or 0)) * 60)
                if chosen.osm_id in combo_info and not pin:
                    done = chosen.eta + timedelta(minutes=chosen.wait_min + (s.dwell_min or 0))
                    for o, kind, p, ev in combo_info[chosen.osm_id]:
                        cov = PlaceCandidate(
                            osm_id=p.osm_id, name=p.name, lat=p.lat, lng=p.lng, tags=p.tags,
                            open_at_eta=hours.open_at(p.tags.get("opening_hours"), done, self.region.timezone),
                            detour_min=0.0, detour_exact=chosen.detour_exact,
                            eta=done, score=0.0,
                            score_breakdown={"detour": 0.0}, matched_stop_ids=[s.id, o.id], evidence=ev,
                            offset_m=chosen.offset_m, along_s=chosen.along_s, parent=chosen.parent,
                            kind="covered", hop_off=chosen.hop_off,
                            combined_note=f"Same {'place' if kind == 'same_poi' else 'building'} as {s.label}"
                                          + (f" ({chosen.parent.name})" if kind == 'container' and chosen.parent else ""))
                        covered[o.id] = (s.id, cov)
            plans[s.id] = StopPlan(request=s, eta_window=EtaWindow(start=win.start, end=win.end, target=win.target),
                                   candidates=top_list, chosen=chosen, added_min=round(added, 1), warnings=swarn)
            chosen_raw[s.id] = chosen_r

        # final pass, in route order: ETAs of chosen stops on the final clock (stops processed
        # later may sit earlier on the route). A prayer stop that is now reached later waits
        # less, which in turn moves every stop after it — hence route order.
        for sid, sp in sorted(((k, v) for k, v in plans.items() if v.chosen), key=lambda kv: kv[1].chosen.along_s):
            ch = sp.chosen
            if sp.covered_by:
                by = plans[sp.covered_by].chosen
                if by:
                    ch.eta = by.eta + timedelta(minutes=by.wait_min + (plans[sp.covered_by].request.dwell_min or 0))
                    ch.open_at_eta = hours.open_at(ch.tags.get("opening_hours"), ch.eta, self.region.timezone)
                continue
            new_eta = clock.at(ch.along_s) + timedelta(minutes=ch.detour_min / 2)
            win = wins.get(sid)
            if win is not None and win.hard_start:
                wait = round(max(0.0, (win.start - new_eta).total_seconds() / 60), 1)
                if abs(wait - ch.wait_min) > 0.15:
                    old = ch.score_breakdown.pop("wait", 0.0)
                    if wait > 0:
                        ch.score_breakdown["wait"] = wait
                    ch.score = round(ch.score - old + wait, 2)
                    ch.wait_min = wait
                    sp.added_min = round(ch.detour_min + wait, 1)
                    clock.set_delay(ch.along_s, (ch.detour_min + wait + (sp.request.dwell_min or 0)) * 60)
            if abs((new_eta - ch.eta).total_seconds()) > 30:
                ch.eta = new_eta
                ch.open_at_eta = hours.open_at(ch.tags.get("opening_hours"), ch.eta, self.region.timezone)
                if ch.open_at_eta is False and sp.request.constraints.open_at_eta:
                    sp.warnings.append("Closed at the updated ETA after earlier stops were added")
                w = sp.eta_window
                timed = sp.request.time_window.type != "any"
                # if the requested time was already outside the trip, that warning says it all
                clamped = any(x.startswith("Requested time is") for x in sp.warnings)
                if timed and not clamped and not (w.start - timedelta(minutes=10) <= ch.eta
                                                  <= w.end + timedelta(minutes=10)):
                    sp.warnings.append(f"Other stops push this to {ch.eta.strftime('%H:%M')}, outside the requested "
                                       f"{w.start.strftime('%H:%M')}–{w.end.strftime('%H:%M')} — pick another option "
                                       "or remove a stop")

        # every stop delays arrival, including ones slotted just past the route end
        arrival = clock.at(max([tl.duration] + [rt for rt, _ in clock.events]) + 1.0) - timedelta(seconds=1.0)
        ordered_plans = [plans[s.id] for s in stops if s.id in plans]

        prayers = self._prayers_on_route(req, tl, clock, depart, arrival, ordered_plans)
        total_added = round(sum(sp.added_min for sp in ordered_plans), 1)

        # Google Maps hand-off: chosen places in route order, deduped
        seq: list[tuple[str, PlaceCandidate]] = []
        seen = set()
        for sp in sorted((sp for sp in ordered_plans if sp.chosen), key=lambda sp: (sp.chosen.along_s, sp.chosen.eta)):
            if sp.chosen.osm_id in seen or sp.covered_by:
                continue
            seen.add(sp.chosen.osm_id)
            seq.append((sp.chosen.name or sp.request.label or "Stop", sp.chosen))
        wps = [(c.lat, c.lng) for _, c in seq]
        url = deeplink.gmaps_url((origin.lat, origin.lng), (dest.lat, dest.lng), wps, mode)
        leg_links: list[LegLink] = []
        if mode == "transit" and seq:
            pts = [(origin.name or "Start", (origin.lat, origin.lng))] + [(n, (c.lat, c.lng)) for n, c in seq] \
                  + [(dest.name or "Destination", (dest.lat, dest.lng))]
            leg_links = [LegLink(label=l, url=u) for l, u in deeplink.leg_urls(pts, mode)]
            warnings.append("Google Maps can't add stops to transit directions — use the per-leg links")
        elif len(wps) > deeplink.MAX_WAYPOINTS:
            warnings.append(f"Google Maps supports at most {deeplink.MAX_WAYPOINTS} waypoints; extra stops dropped")

        rows: list[TimelineRow] = [TimelineRow(kind="depart", time=depart, label=f"Depart {origin.name or ''}".strip())]
        for i, sp in enumerate(ordered_plans):
            if sp.chosen:
                rows.append(TimelineRow(kind="stop", time=sp.chosen.eta, stop_id=sp.request.id,
                                        label=f"{sp.request.label}: {sp.chosen.name or 'Unnamed place'}"))
        for p in prayers:
            if p.time >= depart:
                rows.append(TimelineRow(kind="prayer", time=p.time, prayer=p.name,
                                        label=f"{prayer.DISPLAY.get(p.name, p.name)} starts", stop_id=p.stop_id))
        rows.append(TimelineRow(kind="arrive", time=arrival, label=f"Arrive {dest.name or ''}".strip()))
        rows.sort(key=lambda r: (r.time, {"depart": 0, "prayer": 1, "stop": 2, "arrive": 3}[r.kind]))

        legs_out = [RouteLegOut(mode=l.mode, route_name=l.route_name, from_name=l.from_name, to_name=l.to_name,
                                duration_s=l.duration_s, distance_m=l.distance_m,
                                geometry=[(round(b, 6), round(a, 6)) for a, b in l.coords])
                    for l in route.legs] if mode == "transit" else []
        return TripPlan(
            route=RouteOut(geometry=tl.geometry_lnglat(), duration_s=tl.duration, distance_m=route.distance_m,
                           mode=mode, provider=route.provider, legs=legs_out),
            departure_time=depart, stops=ordered_plans, prayer_times=prayers, timeline=rows,
            total_added_min=total_added, arrival_eta=arrival, gmaps_url=url, gmaps_leg_urls=leg_links,
            warnings=warnings)

    def _pinned_outside(self, s: StopRequest, osm_id: str, tl: Timeline, mode: str, clock: Clock,
                        win: Window) -> Optional[tuple[PlaceCandidate, _Raw]]:
        p = self.places.get_by_osm_id(osm_id)
        if p is None:
            return None
        n = tl.nearest(p.lat, p.lng)
        speed = self.region.mode_speed_kmh.get(mode, 30.0)
        det = estimate_detour_min(n.dist_m, speed, self.region.circuity)
        tags = dict(p.tags)
        if p.name:
            tags.setdefault("name", p.name)
        _, cev = category_evidence(T.get(s.category), tags, s.name_keywords)
        _, dev, weak = dietary_evidence(tags, list(s.constraints.dietary))
        r = _Raw(p, n.dist_m, n.along_t, n.along_m, det, evidence=cev + dev, weak_diet=weak)
        return self._to_candidate(s, r, clock, win), r

    def _prayers_on_route(self, req: TripRequest, tl: Timeline, clock: Clock, depart: datetime,
                          arrival: datetime, plans: list[StopPlan]) -> list[PrayerOnRoute]:
        o = req.origin
        ws = prayer.windows(o.lat, o.lng, depart, arrival, req.prefs.asr_method, req.prefs.prayer_method,
                            self.region.timezone)
        prayer_stops = {str(sp.request.time_window.value).lower(): sp.request.id for sp in plans
                        if sp.request.time_window.type == "prayer"}
        out: list[PrayerOnRoute] = []
        for w in ws:
            if w.start < depart <= w.end:
                pos = tl.position_at(0)
                out.append(PrayerOnRoute(name=w.name, time=w.start, position=Point(lat=pos[0], lng=pos[1]),
                                         route_fraction=0.0, stop_id=prayer_stops.get(w.name),
                                         note=f"window open now (until {w.end.strftime('%H:%M')})"))
            elif depart <= w.start <= arrival:
                rt = min(max(0.0, clock.route_t_of(w.start)), tl.duration)
                pos = tl.position_at(rt)
                out.append(PrayerOnRoute(name=w.name, time=w.start, position=Point(lat=pos[0], lng=pos[1]),
                                         route_fraction=round(tl.fraction_at_time(rt), 4),
                                         stop_id=prayer_stops.get(w.name)))
        return out
