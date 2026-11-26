"""Detour estimates (DESIGN §5.5, D4, D5).

Cheap geometric estimate for every candidate; exact `prev→place→next − prev→next`
via the routing provider for the top few only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from app.core.geo import LatLng


def estimate_detour_min(offset_m: float, speed_kmh: float, circuity: float = 1.3) -> float:
    """drive/cycle/walk: 2 · offset · circuity / speed."""
    return 2 * offset_m * circuity / (speed_kmh * 1000 / 60)


def transit_detour_min(walk_m: float, walk_kmh: float, wait_min: float, circuity: float = 1.3) -> float:
    """transit: walk there and back from the hop-off point + expected wait (headway/2)."""
    return estimate_detour_min(walk_m, walk_kmh, circuity) + wait_min


def neighbour_distance_m(offset_m: float) -> float:
    """How far along the route to place prev/next around a candidate."""
    return max(600.0, 2.5 * offset_m)


RouteSeconds = Callable[[LatLng, LatLng, str, datetime], float]


def exact_detour_min(route_s: RouteSeconds, prev: LatLng, place: LatLng, nxt: LatLng,
                     mode: str, when: datetime) -> float:
    """route(prev→place) + route(place→next) − route(prev→next), in minutes, ≥ 0."""
    a = route_s(prev, place, mode, when)
    b = route_s(place, nxt, mode, when)
    c = route_s(prev, nxt, mode, when)
    return max(0.0, (a + b - c) / 60)


def exact_transit_detour_min(route_s: RouteSeconds, hop_off: LatLng, place: LatLng,
                             wait_min: float, when: datetime) -> float:
    """Hop off, walk there and back, re-board (expected wait)."""
    there = route_s(hop_off, place, "walk", when)
    back = route_s(place, hop_off, "walk", when)
    return max(0.0, (there + back) / 60 + wait_min)
