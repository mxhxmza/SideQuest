from .base import Region

REGION = Region(
    key="singapore",
    name="Singapore",
    timezone="Asia/Singapore",
    bbox=(1.13, 103.59, 1.48, 104.10),
    center=(1.3521, 103.8198),
    prayer_method="SINGAPORE",  # MUIS
    geofabrik_url="https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf",
    boundary_relation_id=536780,
    default_routing=("onemap", "ors", "osrm", "osrm_demo"),
    default_geocoding=("onemap", "photon", "local"),
    mode_speed_kmh={"drive": 30.0, "cycle": 15.0, "walk": 4.8, "transit": 4.8},
    buffer_m={"drive": 2000.0, "cycle": 1200.0, "walk": 800.0, "transit": 800.0},
    circuity=1.3,
    transit_wait_min={"BUS": 5.0, "SUBWAY": 2.5, "TRAM": 3.0, "RAIL": 2.5, "default": 4.0},
)
