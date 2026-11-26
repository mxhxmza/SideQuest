"""Route timeline: cumulative seconds per vertex + interpolation (DESIGN §5.1).

Everything else builds on `position_at(t)` / `time_at(fraction)` and `nearest()`.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

import numpy as np

from app.core.geo import LatLng, Projection
from app.models import Route

TRANSIT_VEHICLE_MODES = {"BUS", "SUBWAY", "TRAM", "RAIL", "FERRY", "LRT", "MRT"}


@dataclass
class Halt:
    """A point where a transit itinerary actually stops (eligible hop-off point, D5)."""
    lat: float
    lng: float
    x: float
    y: float
    t: float
    name: str
    mode: str  # mode of the leg arriving here


@dataclass
class Nearest:
    dist_m: float
    along_t: float
    along_m: float
    seg: int


class Timeline:
    def __init__(self, route: Route, proj: Projection):
        self.route = route
        self.proj = proj
        lats: list[float] = []
        lngs: list[float] = []
        ts: list[float] = []
        leg_of: list[int] = []
        self.halts: list[Halt] = []
        t_run = 0.0
        for li, leg in enumerate(route.legs):
            coords = leg.coords or []
            if not coords:
                continue
            start = leg.start_s if leg.start_s is not None else t_run
            start = max(start, t_run)
            end = leg.end_s if leg.end_s is not None else start + leg.duration_s
            end = max(end, start)
            # Waiting before boarding stays inside this leg: spread the whole
            # [prev_end, end] span over the leg's vertices by length.
            span_start = t_run
            seg_len = [0.0]
            for a, b in zip(coords, coords[1:]):
                ax, ay = proj.to_xy(*a)
                bx, by = proj.to_xy(*b)
                seg_len.append(seg_len[-1] + math.hypot(bx - ax, by - ay))
            total = seg_len[-1]
            wait = start - span_start
            ride = end - start
            for j, (lat, lng) in enumerate(coords):
                if total > 0:
                    t = span_start + wait + ride * (seg_len[j] / total)
                else:
                    t = span_start + wait + (ride if j == len(coords) - 1 else 0.0)
                lats.append(lat)
                lngs.append(lng)
                ts.append(t)
                leg_of.append(li)
            t_run = end
            if leg.mode.upper() in TRANSIT_VEHICLE_MODES:
                for st in leg.stops:
                    x, y = proj.to_xy(st.lat, st.lng)
                    self.halts.append(Halt(st.lat, st.lng, x, y, st.t_s if st.t_s is not None else -1.0,
                                           st.name, leg.mode.upper()))
        if not lats:
            raise ValueError("route has no geometry")
        # enforce non-decreasing time
        for i in range(1, len(ts)):
            if ts[i] < ts[i - 1]:
                ts[i] = ts[i - 1]
        self.lat = np.array(lats)
        self.lng = np.array(lngs)
        xy = [proj.to_xy(a, b) for a, b in zip(lats, lngs)]
        self.x = np.array([p[0] for p in xy])
        self.y = np.array([p[1] for p in xy])
        d = np.hypot(np.diff(self.x), np.diff(self.y))
        self.cum_m = np.concatenate([[0.0], np.cumsum(d)])
        self.t = np.array(ts)
        self.leg_of = leg_of
        self._t_list = ts
        if route.duration_s > self.t[-1] > 0:
            # stretch to the provider's total (rounding / unassigned waiting)
            self.t = self.t * (route.duration_s / self.t[-1])
            self._t_list = [float(v) for v in self.t]
        self.duration = float(self.t[-1])
        self.length = float(self.cum_m[-1])
        # resolve halt times that providers didn't give
        for h in self.halts:
            if h.t < 0:
                h.t = self.nearest_xy(h.x, h.y).along_t

    # -- interpolation -------------------------------------------------------
    def position_at(self, t: float) -> LatLng:
        t = min(max(t, 0.0), float(self.t[-1]))
        i = bisect.bisect_right(self._t_list, t) - 1
        i = min(max(i, 0), len(self._t_list) - 2) if len(self._t_list) > 1 else 0
        if len(self._t_list) == 1:
            return float(self.lat[0]), float(self.lng[0])
        t0, t1 = self._t_list[i], self._t_list[i + 1]
        u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
        return (float(self.lat[i] + u * (self.lat[i + 1] - self.lat[i])),
                float(self.lng[i] + u * (self.lng[i + 1] - self.lng[i])))

    def distance_at(self, t: float) -> float:
        return float(np.interp(t, self.t, self.cum_m))

    def time_at_distance(self, m: float) -> float:
        return float(np.interp(m, self.cum_m, self.t))

    def time_at(self, fraction: float) -> float:
        return self.time_at_distance(min(max(fraction, 0.0), 1.0) * self.length)

    def fraction_at_time(self, t: float) -> float:
        return 0.0 if self.length == 0 else self.distance_at(t) / self.length

    def position_at_distance(self, m: float) -> LatLng:
        return self.position_at(self.time_at_distance(m))

    # -- spatial -------------------------------------------------------------
    def seg_range(self, t0: float, t1: float) -> tuple[int, int]:
        """Segment indices [i0, i1) whose time span overlaps [t0, t1]."""
        n = len(self._t_list)
        if n < 2:
            return 0, 0
        i0 = max(0, bisect.bisect_right(self._t_list, t0) - 1)
        i1 = min(n - 1, bisect.bisect_left(self._t_list, t1) + 0)
        i1 = max(i1, i0 + 1)
        return i0, min(i1, n - 1)

    def bbox_latlng(self, t0: float, t1: float) -> tuple[float, float, float, float]:
        i0, i1 = self.seg_range(t0, t1)
        sl = slice(i0, i1 + 1)
        return (float(self.lat[sl].min()), float(self.lng[sl].min()),
                float(self.lat[sl].max()), float(self.lng[sl].max()))

    def nearest_many(self, px: np.ndarray, py: np.ndarray, t0: float | None = None,
                     t1: float | None = None) -> list[Nearest]:
        """Nearest point on the route (optionally restricted to [t0,t1]) for many points."""
        if t0 is None:
            i0, i1 = 0, len(self.x) - 1
        else:
            i0, i1 = self.seg_range(t0, t1 if t1 is not None else self.duration)
        if i1 <= i0:
            i1 = min(i0 + 1, len(self.x) - 1)
        ax, ay = self.x[i0:i1], self.y[i0:i1]
        bx, by = self.x[i0 + 1:i1 + 1], self.y[i0 + 1:i1 + 1]
        if len(ax) == 0:  # single-vertex route
            d = np.hypot(px - self.x[0], py - self.y[0])
            return [Nearest(float(v), 0.0, 0.0, 0) for v in d]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        L2s = np.where(L2 == 0, 1.0, L2)
        out: list[Nearest] = []
        chunk = max(1, 2_000_000 // max(1, len(ax)))
        for s in range(0, len(px), chunk):
            qx = px[s:s + chunk, None]
            qy = py[s:s + chunk, None]
            u = np.clip(((qx - ax) * dx + (qy - ay) * dy) / L2s, 0.0, 1.0)
            u = np.where(L2 == 0, 0.0, u)
            cx, cy = ax + u * dx, ay + u * dy
            dist = np.hypot(qx - cx, qy - cy)
            j = np.argmin(dist, axis=1)
            rows = np.arange(len(j))
            for r, jj in zip(rows, j):
                seg = i0 + int(jj)
                uu = float(u[r, jj])
                t = float(self.t[seg] + uu * (self.t[seg + 1] - self.t[seg]))
                m = float(self.cum_m[seg] + uu * (self.cum_m[seg + 1] - self.cum_m[seg]))
                out.append(Nearest(float(dist[r, jj]), t, m, seg))
        return out

    def nearest_xy(self, x: float, y: float, t0: float | None = None, t1: float | None = None) -> Nearest:
        return self.nearest_many(np.array([x]), np.array([y]), t0, t1)[0]

    def nearest(self, lat: float, lng: float, t0: float | None = None, t1: float | None = None) -> Nearest:
        x, y = self.proj.to_xy(lat, lng)
        return self.nearest_xy(x, y, t0, t1)

    def leg_mode_at_time(self, t: float) -> str:
        i = max(0, min(bisect.bisect_right(self._t_list, t) - 1, len(self.leg_of) - 1))
        return self.route.legs[self.leg_of[i]].mode.upper()

    def walk_ranges(self) -> list[tuple[float, float]]:
        """Time ranges spent on non-vehicle legs (walking) — for transit trips."""
        out: list[tuple[float, float]] = []
        for li, leg in enumerate(self.route.legs):
            if leg.mode.upper() in TRANSIT_VEHICLE_MODES:
                continue
            idx = [i for i, l in enumerate(self.leg_of) if l == li]
            if idx:
                out.append((float(self.t[idx[0]]), float(self.t[idx[-1]])))
        return out

    def geometry_lnglat(self, tol_m: float = 5.0) -> list[tuple[float, float]]:
        from app.core.geo import simplify_indices
        keep = simplify_indices(list(self.x), list(self.y), tol_m) if len(self.x) > 2000 else range(len(self.x))
        return [(round(float(self.lng[i]), 6), round(float(self.lat[i]), 6)) for i in keep]
