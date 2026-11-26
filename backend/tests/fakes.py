"""Deterministic fake providers for planner/API tests."""
from __future__ import annotations

from datetime import datetime

from app.core.geo import haversine_m
from app.models import Place, Route, RouteLeg, TransitStop

SPEED_KMH = {"drive": 36.0, "walk": 4.8, "cycle": 15.0, "transit": 20.0}


class StraightRouting:
    """Straight line between two points at a fixed speed; counts calls."""
    name = "fake"

    def __init__(self, n_points: int = 50):
        self.n = n_points
        self.calls = 0

    def supports(self, mode) -> bool:
        return True

    def route(self, origin, dest, mode, depart: datetime) -> Route:
        self.calls += 1
        n = self.n
        coords = [(origin[0] + (dest[0] - origin[0]) * i / (n - 1),
                   origin[1] + (dest[1] - origin[1]) * i / (n - 1)) for i in range(n)]
        dist = haversine_m(origin, dest)
        dur = dist / (SPEED_KMH[mode] * 1000 / 3600)
        if mode == "transit":
            # walk 10% / ride 80% (with 3 halts) / walk 10%
            a, b = coords[: n // 10 + 1], coords[n // 10: n - n // 10]
            c = coords[n - n // 10 - 1:]
            w1, ride = dur * 0.1, dur * 0.8
            idx = sorted(set(list(range(0, len(b), 3)) + [len(b) - 1]))
            halts = [TransitStop(name=f"Stop {i}", lat=b[j][0], lng=b[j][1]) for i, j in enumerate(idx)]
            legs = [RouteLeg(mode="WALK", coords=a, duration_s=w1, distance_m=dist * 0.1, start_s=0, end_s=w1),
                    RouteLeg(mode="BUS", coords=b, duration_s=ride - 120, distance_m=dist * 0.8, route_name="179",
                             start_s=w1 + 120, end_s=w1 + ride, stops=halts),
                    RouteLeg(mode="WALK", coords=c, duration_s=dur * 0.1, distance_m=dist * 0.1,
                             start_s=w1 + ride, end_s=dur)]
            return Route(legs=legs, duration_s=dur, distance_m=dist, mode=mode, provider="fake")
        return Route(legs=[RouteLeg(mode=mode.upper(), coords=coords, duration_s=dur, distance_m=dist)],
                     duration_s=dur, distance_m=dist, mode=mode, provider="fake")


# A west→east line across Singapore at lat 1.35 (NTU-ish → Changi-ish)
ORIGIN = (1.3500, 103.6800)
DEST = (1.3500, 103.9900)


def lng_at_km(km: float) -> float:
    return ORIGIN[1] + km / 111.195 / 0.99972


def make_places() -> list[Place]:
    P = []

    def add(pid, osm, name, km, off_m, tags, parent=None, container=False):
        lat = ORIGIN[0] + off_m / 111_195
        P.append(Place(id=pid, osm_id=osm, name=name, lat=lat, lng=lng_at_km(km),
                       tags={**tags, **({"name": name} if name else {})}, parent_id=parent, is_container=container))

    # Mall at km 12 containing a halal restaurant and an electronics shop
    add(1, "w1", "Jurong Point", 12, 300, {"shop": "mall"}, container=True)
    add(2, "n2", "Nasi Lemak House", 12, 310, {"amenity": "restaurant", "diet:halal": "yes",
                                                "opening_hours": "Mo-Su 10:00-22:00"}, parent=1)
    add(3, "n3", "Challenger", 12, 290, {"shop": "electronics", "opening_hours": "Mo-Su 11:00-21:30"}, parent=1)
    # Standalone halal place very close to the route at km 14 (but closed all day)
    add(4, "n4", "Closed Halal Cafe", 14, 50, {"amenity": "cafe", "diet:halal": "yes",
                                               "opening_hours": "Mo-Su 06:00-08:00"})
    # Restaurant without halal evidence (must be excluded for halal requests)
    add(5, "n5", "Pork Ribs Place", 12.5, 20, {"amenity": "restaurant"})
    # Weak evidence only: name hint
    add(6, "n6", "Ali's Nasi Padang", 13, 150, {"amenity": "restaurant"})
    # Mosque at km 25
    add(7, "w7", "Masjid Al-Test", 25, 400, {"amenity": "place_of_worship", "religion": "muslim"})
    # Another mosque far off route (outside buffer)
    add(8, "n8", "Masjid Far", 25, 5000, {"amenity": "place_of_worship", "religion": "muslim"})
    # Electronics shop standalone at km 30, 1 km off route
    add(9, "n9", "Gadget Hut", 30, 1000, {"shop": "mobile_phone"})
    # Duplicate node+way of the same mosque within 30 m
    add(10, "n10", "Masjid Al-Test", 25, 410, {"amenity": "place_of_worship"})
    return P
