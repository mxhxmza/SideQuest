"""In-memory PlacesProvider for deterministic tests (DESIGN §12)."""
from __future__ import annotations

from typing import Optional

from app.core.tags import matches_filters, matches_name
from app.models import Place
from app.providers.base import BBox


class FakePlaces:
    name = "fake"

    def __init__(self, places: list[Place]):
        self.places = places

    def query(self, bbox: BBox, filters: list[dict], name_keywords: tuple[str, ...] = ()) -> list[Place]:
        a, b, c, d = bbox
        return [p for p in self.places
                if a <= p.lat <= c and b <= p.lng <= d
                and (matches_filters(p.tags, filters) or matches_name(p.name, name_keywords))]

    def children(self, parent_id: int) -> list[Place]:
        return [p for p in self.places if p.parent_id == parent_id]

    def get(self, place_id: int) -> Optional[Place]:
        return next((p for p in self.places if p.id == place_id), None)

    def get_by_osm_id(self, osm_id: str) -> Optional[Place]:
        return next((p for p in self.places if p.osm_id == osm_id), None)

    def search_name(self, q: str, limit: int = 8) -> list[Place]:
        return [p for p in self.places if p.name and q.lower() in p.name.lower()][:limit]

    def info(self) -> dict:
        return {"region": "fake", "poi_count": str(len(self.places))}
