import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.cache import TTLCache
from app.config import Settings
from app.deps import Container
from app.providers.geocoding.chain import ChainGeocoding, LocalPoiGeocoding
from app.providers.llm.service import ParseService
from app.providers.places.fake import FakePlaces
from app.providers.routing.chain import CachedRouting, FallbackRouting
from app.providers.routing.onemap import OneMapAuth
from app.regions import get_region
from tests.fakes import DEST, ORIGIN, StraightRouting, make_places


@pytest.fixture
def client(monkeypatch):
    s = Settings(_env_file=None)
    places = FakePlaces(make_places())
    cache = TTLCache(None)
    routing = FallbackRouting([StraightRouting()])
    c = Container(settings=s, region=get_region("singapore"), cache=cache, routing=routing,
                  cached_routing=CachedRouting(routing, cache, 60),
                  geocoder=ChainGeocoding([LocalPoiGeocoding(places)]), places=places, places_error=None,
                  parser=ParseService(s), onemap_auth=OneMapAuth("", ""))
    monkeypatch.setattr(main, "container", lambda: c)
    return TestClient(main.app)


def test_health(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["routing"]["drive"] == ["fake"]


def test_parse_then_plan(client):
    p = client.post("/api/parse", json={"text": "halal lunch around 12:50, mosque at zohor, phone charger"}).json()
    assert p["backend_used"] == "rules"
    assert [s["category"] for s in p["stops"]] == ["meal", "mosque", "charger"]
    assert p["stops"][0]["osm_filters"]  # filled deterministically
    trip = {"origin": {"lat": ORIGIN[0], "lng": ORIGIN[1], "name": "A"},
            "destination": {"lat": DEST[0], "lng": DEST[1], "name": "B"},
            "mode": "drive", "departure_time": "2026-11-27T12:30:00+08:00", "stops": p["stops"]}
    r = client.post("/api/plan", json=trip)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["stops"][0]["chosen"]["name"] == "Nasi Lemak House"
    assert plan["gmaps_url"].startswith("https://www.google.com/maps/dir/")
    # pin another option and replan
    trip["pinned"] = {"s1": "n6"}
    plan2 = client.post("/api/plan", json=trip).json()
    assert plan2["stops"][0]["chosen"]["osm_id"] == "n6"


def test_plan_requires_tz(client):
    trip = {"origin": {"lat": 1.35, "lng": 103.7}, "destination": {"lat": 1.35, "lng": 103.9},
            "departure_time": "2026-11-27T12:30:00"}
    assert client.post("/api/plan", json=trip).status_code == 422


def test_prayer_times_and_geocode(client):
    r = client.get("/api/prayer-times", params={"lat": 1.35, "lng": 103.8, "date": "2026-11-27"}).json()
    assert [x["name"] for x in r] == ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
    g = client.get("/api/geocode", params={"q": "jurong"}).json()
    assert g[0]["name"] == "Jurong Point"


def test_parse_llm_fallback(client):
    r = client.post("/api/parse", json={"text": "toilet", "backend": "openai_compat"}).json()
    assert r["backend_used"] == "rules" and r["warnings"]
