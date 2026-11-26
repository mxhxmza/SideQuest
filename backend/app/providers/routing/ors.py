"""OpenRouteService fallback (free key): drive / walk / cycle only — no transit."""
from __future__ import annotations

from datetime import datetime

from app.models import Mode, Route, RouteLeg
from app.providers.base import LatLng, ProviderError
from app.providers.http import client

PROFILE = {"drive": "driving-car", "walk": "foot-walking", "cycle": "cycling-regular"}


class ORSRouting:
    name = "ors"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def supports(self, mode: Mode) -> bool:
        return bool(self.api_key) and mode in PROFILE

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route:
        r = client().post(
            f"https://api.openrouteservice.org/v2/directions/{PROFILE[mode]}/geojson",
            json={"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]},
            headers={"Authorization": self.api_key})
        if r.status_code != 200:
            raise ProviderError(f"ORS HTTP {r.status_code}: {r.text[:200]}")
        feat = (r.json().get("features") or [None])[0]
        if not feat:
            raise ProviderError("ORS: no route")
        coords = [(c[1], c[0]) for c in feat["geometry"]["coordinates"]]
        s = feat["properties"].get("summary", {})
        dur, dist = float(s.get("duration", 0)), float(s.get("distance", 0))
        leg = RouteLeg(mode=mode.upper(), coords=coords, duration_s=dur, distance_m=dist)
        return Route(legs=[leg], duration_s=dur, distance_m=dist, mode=mode, provider="ors")
