"""Provider interfaces (DESIGN §3). core/ depends only on these Protocols."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from app.models import GeocodeResult, Mode, ParseContext, Place, Route, StopRequest

LatLng = tuple[float, float]
BBox = tuple[float, float, float, float]  # min_lat, min_lng, max_lat, max_lng


class ProviderError(RuntimeError):
    pass


@runtime_checkable
class RoutingProvider(Protocol):
    name: str

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route: ...

    def supports(self, mode: Mode) -> bool: ...


@runtime_checkable
class GeocodingProvider(Protocol):
    name: str

    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]: ...


@runtime_checkable
class PlacesProvider(Protocol):
    def query(self, bbox: BBox, filters: list[dict], name_keywords: tuple[str, ...] = ()) -> list[Place]: ...

    def children(self, parent_id: int) -> list[Place]: ...

    def get(self, place_id: int) -> Optional[Place]: ...

    def get_by_osm_id(self, osm_id: str) -> Optional[Place]: ...

    def info(self) -> dict: ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def parse(self, text: str, ctx: ParseContext) -> list[StopRequest]: ...
