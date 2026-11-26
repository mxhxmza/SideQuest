"""PlacesProvider over the imported OSM SQLite + R*Tree DB (D2)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from app.core.tags import ANY, matches_filters, matches_name
from app.models import Place
from app.providers.base import BBox

_COLS = "p.id, p.osm_id, p.name, p.lat, p.lng, p.tags, p.parent_id, p.is_container"


def _row(r) -> Place:
    return Place(id=r[0], osm_id=r[1], name=r[2], lat=r[3], lng=r[4], tags=json.loads(r[5]),
                 parent_id=r[6], is_container=bool(r[7]))


class OsmSqlitePlaces:
    name = "osm_sqlite"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"POI DB not found at {self.path}. Run backend/scripts/import_osm.py")
        self._local = threading.local()

    @property
    def db(self) -> sqlite3.Connection:
        c = getattr(self._local, "db", None)
        if c is None:
            c = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            self._local.db = c
        return c

    def query(self, bbox: BBox, filters: list[dict], name_keywords: tuple[str, ...] = ()) -> list[Place]:
        min_lat, min_lng, max_lat, max_lng = bbox
        found: dict[int, Place] = {}
        box = "r.min_lat <= ? AND r.max_lat >= ? AND r.min_lng <= ? AND r.max_lng >= ?"
        box_args = (max_lat, min_lat, max_lng, min_lng)
        for f in filters:
            # use the first key of each filter as the indexed predicate, check the rest in Python
            k, values = next(iter(f.items()))
            if ANY in values:
                sql = (f"SELECT DISTINCT {_COLS} FROM poi_rtree r JOIN pois p ON p.id = r.id "
                       f"JOIN poi_tags t ON t.poi_id = p.id WHERE {box} AND t.k = ?")
                args = (*box_args, k)
            else:
                ph = ",".join("?" * len(values))
                sql = (f"SELECT DISTINCT {_COLS} FROM poi_rtree r JOIN pois p ON p.id = r.id "
                       f"JOIN poi_tags t ON t.poi_id = p.id WHERE {box} AND t.k = ? AND t.v IN ({ph})")
                args = (*box_args, k, *values)
            for r in self.db.execute(sql, args):
                if r[0] in found:
                    continue
                pl = _row(r)
                if matches_filters(pl.tags, [f]):
                    found[pl.id] = pl
        if name_keywords:
            like = " OR ".join("p.name LIKE ?" for _ in name_keywords)
            sql = f"SELECT {_COLS} FROM poi_rtree r JOIN pois p ON p.id = r.id WHERE {box} AND ({like})"
            for r in self.db.execute(sql, (*box_args, *[f"%{k}%" for k in name_keywords])):
                if r[0] not in found and matches_name(r[2], name_keywords):
                    found[r[0]] = _row(r)
        return list(found.values())

    def children(self, parent_id: int) -> list[Place]:
        return [_row(r) for r in self.db.execute(f"SELECT {_COLS} FROM pois p WHERE p.parent_id = ?", (parent_id,))]

    def get(self, place_id: int) -> Optional[Place]:
        r = self.db.execute(f"SELECT {_COLS} FROM pois p WHERE p.id = ?", (place_id,)).fetchone()
        return _row(r) if r else None

    def get_by_osm_id(self, osm_id: str) -> Optional[Place]:
        r = self.db.execute(f"SELECT {_COLS} FROM pois p WHERE p.osm_id = ?", (osm_id,)).fetchone()
        return _row(r) if r else None

    def search_name(self, q: str, limit: int = 8) -> list[Place]:
        rows = self.db.execute(
            f"SELECT {_COLS} FROM pois p WHERE p.name LIKE ? "
            "ORDER BY p.is_container DESC, length(p.name) LIMIT ?", (f"%{q}%", limit)).fetchall()
        return [_row(r) for r in rows]

    def info(self) -> dict:
        try:
            return dict(self.db.execute("SELECT key, value FROM meta").fetchall())
        except sqlite3.Error as e:
            return {"error": str(e)}
