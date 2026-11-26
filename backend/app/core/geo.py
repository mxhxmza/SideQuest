"""Geometry helpers: local equirectangular projection (D10), polyline codec, distances."""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_R = 6371008.8
M_PER_DEG = EARTH_R * math.pi / 180

LatLng = tuple[float, float]


@dataclass(frozen=True)
class Projection:
    lat0: float
    lng0: float

    @property
    def k(self) -> float:
        return math.cos(math.radians(self.lat0))

    def to_xy(self, lat: float, lng: float) -> tuple[float, float]:
        return ((lng - self.lng0) * M_PER_DEG * self.k, (lat - self.lat0) * M_PER_DEG)

    def to_latlng(self, x: float, y: float) -> LatLng:
        return (self.lat0 + y / M_PER_DEG, self.lng0 + x / (M_PER_DEG * self.k))

    def expand_bbox(self, min_lat: float, min_lng: float, max_lat: float, max_lng: float,
                    metres: float) -> tuple[float, float, float, float]:
        dlat = metres / M_PER_DEG
        dlng = metres / (M_PER_DEG * self.k)
        return (min_lat - dlat, min_lng - dlng, max_lat + dlat, max_lng + dlng)


def haversine_m(a: LatLng, b: LatLng) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def point_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    """Distance from P to segment AB and the projection parameter u in [0,1]."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), 0.0
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy)), u


def decode_polyline(s: str, precision: int = 5) -> list[LatLng]:
    coords: list[LatLng] = []
    idx = lat = lng = 0
    factor = 10 ** precision
    while idx < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[idx]) - 63
                idx += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += d
            else:
                lng += d
        coords.append((lat / factor, lng / factor))
    return coords


def encode_polyline(coords: list[LatLng], precision: int = 5) -> str:
    factor = 10 ** precision
    out: list[str] = []
    plat = plng = 0
    for lat, lng in coords:
        ilat, ilng = round(lat * factor), round(lng * factor)
        for d in (ilat - plat, ilng - plng):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plng = ilat, ilng
    return "".join(out)


def simplify_indices(xs: list[float], ys: list[float], tol_m: float) -> list[int]:
    """Douglas–Peucker on projected coords; returns kept indices (for compact output)."""
    n = len(xs)
    if n <= 2:
        return list(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        best, bi = 0.0, -1
        for i in range(a + 1, b):
            d, _ = point_segment(xs[i], ys[i], xs[a], ys[a], xs[b], ys[b])
            if d > best:
                best, bi = d, i
        if best > tol_m and bi > 0:
            keep[bi] = True
            stack.append((a, bi))
            stack.append((bi, b))
    return [i for i in range(n) if keep[i]]
