"""Keyless Google Maps deep links (DESIGN §8 screen 4, §9)."""
from __future__ import annotations

from urllib.parse import urlencode

TRAVELMODE = {"drive": "driving", "walk": "walking", "cycle": "bicycling", "transit": "transit"}
MAX_WAYPOINTS = 9


def _fmt(lat: float, lng: float) -> str:
    return f"{lat:.6f},{lng:.6f}"


def gmaps_url(origin: tuple[float, float], destination: tuple[float, float],
              waypoints: list[tuple[float, float]], mode: str) -> str:
    params = {"api": "1", "origin": _fmt(*origin), "destination": _fmt(*destination),
              "travelmode": TRAVELMODE.get(mode, "driving")}
    # Google ignores waypoints for transit; callers use per-leg links instead.
    if waypoints and mode != "transit":
        params["waypoints"] = "|".join(_fmt(*w) for w in waypoints[:MAX_WAYPOINTS])
    return "https://www.google.com/maps/dir/?" + urlencode(params, safe=",|")


def leg_urls(points: list[tuple[str, tuple[float, float]]], mode: str) -> list[tuple[str, str]]:
    """One link per consecutive pair: [(label, url)]."""
    out = []
    for (na, a), (nb, b) in zip(points, points[1:]):
        out.append((f"{na} → {nb}", gmaps_url(a, b, [], mode)))
    return out
