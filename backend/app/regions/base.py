from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    timezone: str
    # (min_lat, min_lng, max_lat, max_lng)
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    prayer_method: str
    geofabrik_url: str
    boundary_relation_id: int
    default_routing: tuple[str, ...]
    default_geocoding: tuple[str, ...]
    # km/h, used for cheap detour estimates (DESIGN §5.5)
    mode_speed_kmh: dict[str, float] = field(default_factory=dict)
    # metres, spatial buffer around the route segment (DESIGN §5.4)
    buffer_m: dict[str, float] = field(default_factory=dict)
    circuity: float = 1.3
    # expected wait when re-boarding public transport (headway / 2), minutes
    transit_wait_min: dict[str, float] = field(default_factory=dict)
