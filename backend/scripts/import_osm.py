"""Import OSM POIs for a region into SQLite + R*Tree.

Usage (from repo root or backend/):
    python backend/scripts/import_osm.py                 # download (if missing) + import
    python backend/scripts/import_osm.py --pbf path.pbf  # use an existing extract
    python backend/scripts/import_osm.py --out data/pois.sqlite

Pipeline (see DESIGN.md §2, D2):
  1. Geofabrik `malaysia-singapore-brunei` extract (there is no SG-only extract).
  2. Relation pass: find the Singapore admin boundary and multipolygon malls; remember member ways.
  3. Main pass (node locations cached): collect tagged nodes/ways inside the region bbox,
     closed-way polygons for containers (malls / large named retail buildings), and the
     member-way geometries needed to assemble relation polygons.
  4. Clip to the Singapore boundary, dedupe, assign `parent_id` (POI inside a container).
  5. Write `pois`, `poi_tags`, `poi_rtree`, `meta`.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import osmium
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import linemerge, polygonize, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.regions import get_region  # noqa: E402

# Keys that make a node/way interesting as a POI.
POI_KEYS = ("amenity", "shop", "leisure", "healthcare", "religion", "diet:halal", "cuisine")
# Values we never want (noise for a stop planner).
SKIP_VALUES = {
    "amenity": {"bench", "waste_basket", "bicycle_parking", "vending_machine", "recycling",
                "waste_disposal", "shelter", "telephone", "post_box", "clock", "drinking_water",
                "motorcycle_parking", "parking_entrance", "parking_space", "loading_dock",
                "grit_bin", "letter_box"},
}
CONTAINER_BUILDINGS = {"retail", "commercial", "yes", "mall"}
CONTAINER_MIN_AREA_M2 = 15000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"downloading {url} -> {dest}")
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total and done % (25 << 20) < (1 << 20):
                log(f"  {done / total:.0%}")
    tmp.replace(dest)


class Proj:
    """Local equirectangular projection (metres) — D10."""

    def __init__(self, lat0: float, lng0: float):
        self.k = math.cos(math.radians(lat0))
        self.lat0, self.lng0 = lat0, lng0
        self.m = 6371008.8 * math.pi / 180

    def area_m2(self, poly: Polygon) -> float:
        return poly.area * self.m * self.m * self.k


def tags_dict(obj) -> dict[str, str]:
    return {t.k: t.v for t in obj.tags}


def is_poi(tags: dict[str, str]) -> bool:
    for k in POI_KEYS:
        v = tags.get(k)
        if v is None:
            continue
        if v in SKIP_VALUES.get(k, ()):
            continue
        return True
    return False


def is_container_tags(tags: dict[str, str]) -> bool:
    if tags.get("shop") == "mall":
        return True
    return "name" in tags and tags.get("building") in CONTAINER_BUILDINGS


def assemble(ways: list[list[tuple[float, float]]]) -> Polygon | None:
    lines = [LineString(w) for w in ways if len(w) >= 2]
    if not lines:
        return None
    merged = linemerge(lines)
    polys = list(polygonize(merged))
    if not polys:
        return None
    return unary_union(polys)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="singapore")
    ap.add_argument("--pbf", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    region = get_region(args.region)
    pbf = args.pbf or (ROOT / "data" / region.geofabrik_url.rsplit("/", 1)[-1])
    out = args.out or (ROOT / "data" / "pois.sqlite")
    if not pbf.exists():
        download(region.geofabrik_url, pbf)

    min_lat, min_lng, max_lat, max_lng = region.bbox
    proj = Proj(*region.center)

    def in_bbox(lat: float, lng: float) -> bool:
        return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng

    # ---- pass 1: relations ------------------------------------------------
    log("pass 1: relations")
    boundary_ways: set[int] = set()
    rel_containers: dict[int, dict] = {}  # rel id -> {tags, ways}
    for rel in osmium.FileProcessor(str(pbf), osmium.osm.RELATION):
        tags = tags_dict(rel)
        if rel.id == region.boundary_relation_id:
            boundary_ways = {m.ref for m in rel.members if m.type == "w" and m.role in ("outer", "")}
        elif tags.get("type") == "multipolygon" and (is_container_tags(tags) or is_poi(tags)):
            ways = [m.ref for m in rel.members if m.type == "w" and m.role in ("outer", "")]
            rel_containers[rel.id] = {"tags": tags, "ways": ways}
    rel_way_ids = {w for r in rel_containers.values() for w in r["ways"]}
    log(f"  boundary member ways: {len(boundary_ways)}, multipolygon POIs: {len(rel_containers)}")

    # ---- pass 2: nodes + ways -------------------------------------------
    log("pass 2: nodes and ways (this takes a few minutes)")
    pois: list[dict] = []
    containers: list[dict] = []
    way_geoms: dict[int, list[tuple[float, float]]] = {}
    fp = osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations()
    n_seen = 0
    for obj in fp:
        n_seen += 1
        if n_seen % 5_000_000 == 0:
            log(f"  {n_seen:,} objects")
        if obj.is_node():
            if not obj.tags:
                continue
            loc = obj.location
            if not loc.valid() or not in_bbox(loc.lat, loc.lon):
                continue
            tags = tags_dict(obj)
            if is_poi(tags):
                pois.append({"osm_id": f"n{obj.id}", "lat": loc.lat, "lng": loc.lon, "tags": tags})
            continue

        # way
        wid = obj.id
        need_geom = wid in boundary_ways or wid in rel_way_ids
        tags = tags_dict(obj) if obj.tags else {}
        poi = bool(tags) and is_poi(tags)
        container = bool(tags) and is_container_tags(tags) and obj.is_closed()
        if not (need_geom or poi or container):
            continue
        try:
            coords = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
        except osmium.InvalidLocationError:
            continue
        if len(coords) < 2:
            continue
        if need_geom:
            way_geoms[wid] = coords
        if not (poi or container):
            continue
        lng_c = sum(c[0] for c in coords) / len(coords)
        lat_c = sum(c[1] for c in coords) / len(coords)
        if not in_bbox(lat_c, lng_c):
            continue
        poly = Polygon(coords) if obj.is_closed() and len(coords) >= 4 else None
        if poly is not None and poly.is_valid:
            c = poly.representative_point()
            lng_c, lat_c = c.x, c.y
        rec = {"osm_id": f"w{wid}", "lat": lat_c, "lng": lng_c, "tags": tags}
        if container and poly is not None and poly.is_valid:
            a = proj.area_m2(poly)
            if tags.get("shop") == "mall" or a >= CONTAINER_MIN_AREA_M2:
                rec["poly"] = poly
                rec["area_m2"] = a
                containers.append(rec)
        if poi or "poly" in rec:
            pois.append(rec)
    log(f"  seen {n_seen:,} objects; POIs {len(pois):,}, containers {len(containers):,}")

    # ---- relation polygons ----------------------------------------------
    boundary = None
    if boundary_ways:
        boundary = assemble([way_geoms[w] for w in boundary_ways if w in way_geoms])
    if boundary is None or boundary.is_empty:
        log("  WARNING: boundary relation not assembled; falling back to bbox")
        boundary = box(min_lng, min_lat, max_lng, max_lat)
    else:
        log(f"  boundary area {proj.area_m2(boundary) / 1e6:.0f} km² (incl. territorial waters)")

    for rid, r in rel_containers.items():
        poly = assemble([way_geoms[w] for w in r["ways"] if w in way_geoms])
        if poly is None or poly.is_empty:
            continue
        c = poly.representative_point()
        if not in_bbox(c.y, c.x):
            continue
        rec = {"osm_id": f"r{rid}", "lat": c.y, "lng": c.x, "tags": r["tags"]}
        if is_container_tags(r["tags"]):
            rec["poly"] = poly
            rec["area_m2"] = proj.area_m2(poly)
            containers.append(rec)
        pois.append(rec)

    # ---- clip to region ---------------------------------------------------
    from shapely.prepared import prep
    pb = prep(boundary)
    before = len(pois)
    pois = [p for p in pois if pb.contains(Point(p["lng"], p["lat"]))]
    containers = [c for c in containers if pb.contains(Point(c["lng"], c["lat"]))]
    log(f"  clipped to region: {before:,} -> {len(pois):,} POIs")

    # ---- parent_id (smallest container that contains the POI) -------------
    for i, p in enumerate(pois):
        p["id"] = i + 1
    cont_polys = [c["poly"] for c in containers]
    tree = STRtree(cont_polys) if cont_polys else None
    n_parented = 0
    if tree is not None:
        for p in pois:
            pt = Point(p["lng"], p["lat"])
            best = None
            for idx in tree.query(pt, predicate="within"):
                c = containers[int(idx)]
                if c is p:
                    continue
                if best is None or c["area_m2"] < best["area_m2"]:
                    best = c
            if best is not None and best.get("area_m2", 0) > p.get("area_m2", 0):
                p["parent_id"] = best["id"]
                n_parented += 1
    log(f"  POIs inside a container: {n_parented:,}")

    # ---- write ------------------------------------------------------------
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(
        """
        CREATE TABLE pois (id INTEGER PRIMARY KEY, osm_id TEXT NOT NULL, name TEXT,
                           lat REAL NOT NULL, lng REAL NOT NULL, tags TEXT NOT NULL,
                           parent_id INTEGER, is_container INTEGER NOT NULL DEFAULT 0,
                           area_m2 REAL);
        CREATE TABLE poi_tags (poi_id INTEGER NOT NULL, k TEXT NOT NULL, v TEXT NOT NULL);
        CREATE VIRTUAL TABLE poi_rtree USING rtree(id, min_lat, max_lat, min_lng, max_lng);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    for p in pois:
        db.execute(
            "INSERT INTO pois VALUES (?,?,?,?,?,?,?,?,?)",
            (p["id"], p["osm_id"], p["tags"].get("name"), p["lat"], p["lng"],
             json.dumps(p["tags"], ensure_ascii=False), p.get("parent_id"),
             1 if "poly" in p else 0, p.get("area_m2")),
        )
        db.executemany("INSERT INTO poi_tags VALUES (?,?,?)",
                       [(p["id"], k, v) for k, v in p["tags"].items()
                        if k in POI_KEYS or k.startswith("diet:") or k in ("brand", "building")])
        db.execute("INSERT INTO poi_rtree VALUES (?,?,?,?,?)",
                   (p["id"], p["lat"], p["lat"], p["lng"], p["lng"]))
    db.executescript(
        """
        CREATE INDEX poi_tags_kv ON poi_tags (k, v);
        CREATE INDEX poi_tags_id ON poi_tags (poi_id);
        CREATE INDEX pois_parent ON pois (parent_id);
        CREATE INDEX pois_osm ON pois (osm_id);
        CREATE INDEX pois_name ON pois (name COLLATE NOCASE);
        """
    )
    import os
    try:
        hdr = osmium.io.Reader(str(pbf), osmium.osm.NOTHING).header()
        data_ts = hdr.get("osmosis_replication_timestamp") or ""
    except Exception:
        data_ts = ""
    meta = {
        "region": region.key,
        "source": region.geofabrik_url,
        "data_timestamp": data_ts or datetime.fromtimestamp(os.path.getmtime(pbf), timezone.utc).isoformat(),
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "poi_count": str(len(pois)),
        "container_count": str(len(containers)),
        "schema_version": "1",
    }
    db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    db.commit()
    db.close()
    if out.exists():
        out.unlink()
    tmp.replace(out)
    log(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
