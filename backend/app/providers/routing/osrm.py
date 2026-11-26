"""Keyless OSRM fallback (FOSSGIS community server routing.openstreetmap.de, and the
OSRM demo server for driving).

Not in the original stack: added so the app works with zero credentials (DECISIONS D11).
drive / walk / cycle only; low volume (token bucket), results cached, and
duration-only requests (overview=false) for exact-detour checks.
"""
from __future__ import annotations

from datetime import datetime

from app.cache import TokenBucket
from app.core.geo import decode_polyline
from app.models import Mode, Route, RouteLeg
from app.providers.base import LatLng, ProviderError
from app.providers.http import client

FOSSGIS_PATHS = {"drive": "routed-car/route/v1/driving", "walk": "routed-foot/route/v1/driving",
                 "cycle": "routed-bike/route/v1/driving"}
DEMO_PATHS = {"drive": "route/v1/driving"}


class OSRMRouting:
    def __init__(self, base_url: str, paths: dict[str, str] | None = None, name: str = "osrm",
                 per_minute: float = 90, matrix: bool = True):
        self.base = base_url.rstrip("/")
        self.paths = paths or FOSSGIS_PATHS
        self.name = name
        self.bucket = TokenBucket(per_minute, burst=6)
        # FOSSGIS throttles its table service to ~1 request / 10 s, so it is
        # disabled there; pairwise duration-only route calls are faster.
        self.matrix = matrix

    def supports(self, mode: Mode) -> bool:
        return bool(self.base) and mode in self.paths

    def _get(self, origin: LatLng, dest: LatLng, mode: Mode, overview: str) -> dict:
        url = (f"{self.base}/{self.paths[mode]}/"
               f"{origin[1]:.6f},{origin[0]:.6f};{dest[1]:.6f},{dest[0]:.6f}")
        self.bucket.take()
        r = client().get(url, params={"overview": overview, "geometries": "polyline"})
        if r.status_code != 200:
            reason = "rate limited" if r.status_code == 429 else r.text[:120].replace("\n", " ")
            raise ProviderError(f"{self.name} HTTP {r.status_code} ({reason})")
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ProviderError(f"{self.name}: {data.get('code')} {data.get('message', '')}")
        return data["routes"][0]

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route:
        rt = self._get(origin, dest, mode, "full")
        coords = decode_polyline(rt["geometry"], 5)
        dur, dist = float(rt["duration"]), float(rt["distance"])
        leg = RouteLeg(mode=mode.upper(), coords=coords, duration_s=dur, distance_m=dist)
        return Route(legs=[leg], duration_s=dur, distance_m=dist, mode=mode, provider=self.name)

    def duration_s(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> float:
        return float(self._get(origin, dest, mode, "false")["duration"])

    def matrix_s(self, points: list[LatLng], mode: Mode) -> list[list[float]]:
        """All-pairs durations in one request (OSRM table service)."""
        if not self.matrix:
            raise NotImplementedError(f"{self.name}: table service disabled")
        path = self.paths[mode].replace("route/v1", "table/v1")
        coords = ";".join(f"{p[1]:.6f},{p[0]:.6f}" for p in points)
        self.bucket.take()
        r = client().get(f"{self.base}/{path}/{coords}", params={"annotations": "duration"})
        if r.status_code != 200:
            raise ProviderError(f"{self.name} table HTTP {r.status_code}")
        data = r.json()
        if data.get("code") != "Ok":
            raise ProviderError(f"{self.name} table: {data.get('code')}")
        return [[float(v) if v is not None else float("nan") for v in row] for row in data["durations"]]
