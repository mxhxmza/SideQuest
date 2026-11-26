"""Wires concrete providers from settings + region config (the only place that does)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.cache import TTLCache
from app.config import Settings, get_settings
from app.core.planner import Planner
from app.providers.geocoding.chain import ChainGeocoding, LocalPoiGeocoding
from app.providers.geocoding.onemap import OneMapGeocoding
from app.providers.geocoding.photon import PhotonGeocoding
from app.providers.llm.service import ParseService
from app.providers.places.osm_sqlite import OsmSqlitePlaces
from app.providers.routing.chain import CachedRouting, FallbackRouting
from app.providers.routing.onemap import OneMapAuth, OneMapRouting
from app.providers.routing.ors import ORSRouting
from app.providers.routing.osrm import DEMO_PATHS, OSRMRouting
from app.regions import Region, get_region


@dataclass
class Container:
    settings: Settings
    region: Region
    cache: TTLCache
    routing: FallbackRouting
    cached_routing: CachedRouting
    geocoder: ChainGeocoding
    places: Optional[OsmSqlitePlaces]
    places_error: Optional[str]
    parser: ParseService
    onemap_auth: OneMapAuth

    def planner(self) -> Planner:
        if self.places is None:
            raise RuntimeError(self.places_error or "POI database unavailable")
        return Planner(self.cached_routing, self.places, self.region)


def build(settings: Settings) -> Container:
    region = get_region(settings.region)
    cache = TTLCache(settings.path(settings.cache_db_path))
    auth = OneMapAuth(settings.onemap_email, settings.onemap_password)
    available = {
        "onemap": OneMapRouting(auth),
        "ors": ORSRouting(settings.ors_api_key),
        "osrm": OSRMRouting(settings.osrm_base_url, matrix=False),
        "osrm_demo": OSRMRouting(settings.osrm_demo_url, DEMO_PATHS, name="osrm_demo"),
    }
    routing = FallbackRouting([available[k] for k in region.default_routing if k in available])
    cached = CachedRouting(routing, cache, settings.route_cache_ttl_s)
    places, places_error = None, None
    try:
        places = OsmSqlitePlaces(settings.path(settings.poi_db_path))
    except FileNotFoundError as e:
        places_error = str(e)
    geo_available = {
        "onemap": OneMapGeocoding(auth),
        "photon": PhotonGeocoding(settings.photon_url, region.bbox, region.center),
    }
    if places is not None:
        geo_available["local"] = LocalPoiGeocoding(places)
    geocoder = ChainGeocoding([geo_available[k] for k in region.default_geocoding if k in geo_available],
                              cache, settings.geocode_cache_ttl_s)
    return Container(settings, region, cache, routing, cached, geocoder, places, places_error,
                     ParseService(settings), auth)


@lru_cache
def container() -> Container:
    return build(get_settings())
