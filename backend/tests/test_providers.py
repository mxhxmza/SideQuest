import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.cache import TTLCache
from app.core.geo import Projection
from app.core.timeline import Timeline
from app.providers.base import ProviderError
from app.providers.routing.chain import CachedRouting, FallbackRouting
from app.providers.routing.onemap import OneMapAuth, OneMapRouting, parse_direct, parse_pt
from tests.fakes import StraightRouting

FIX = Path(__file__).parent / "fixtures" / "onemap"
TZ = ZoneInfo("Asia/Singapore")
DEP = datetime(2026, 11, 27, 12, 30, tzinfo=TZ)


def load(name):
    return json.loads((FIX / name).read_text())


def test_parse_drive_fixture():
    data = load("ntu_changi_drive.json")
    r = parse_direct(data, "drive")
    assert r.provider == "onemap" and r.duration_s > 0
    if "_recorded" in data:
        return
    assert r.duration_s == 2520 and len(r.legs[0].coords) == 7
    assert r.legs[0].coords[0] == pytest.approx((1.34831, 103.68312), abs=1e-5)


def test_parse_pt_fixture_and_timeline():
    data = load("jurongwest_sultan_pt.json")
    if "_recorded" in data:  # real recording: only check structure
        r = parse_pt(data, datetime.fromisoformat(data["_recorded"]["depart"]))
        assert r.legs and r.duration_s > 0
        assert Timeline(r, Projection(1.3521, 103.8198)).duration > 0
        return
    r = parse_pt(data, DEP)
    assert [l.mode for l in r.legs] == ["WALK", "SUBWAY", "WALK"]
    sub = r.legs[1]
    assert sub.start_s == pytest.approx(9 * 60) and sub.end_s == pytest.approx(41 * 60)
    assert [s.name for s in sub.stops][1] == "JURONG EAST MRT STATION"
    assert r.duration_s == pytest.approx(50 * 60)
    tl = Timeline(r, Projection(1.3521, 103.8198))
    assert len(tl.halts) == 5
    assert tl.halts[1].t == pytest.approx(15 * 60)
    # waiting 6..9 min happens at Boon Lay station
    lat, lng = tl.position_at(8 * 60)
    assert (lat, lng) == pytest.approx((1.3386, 103.7058), abs=1e-4)


def test_onemap_with_mock_transport():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        if req.url.path.endswith("getToken"):
            return httpx.Response(200, json={"access_token": "tok", "expiry_timestamp": str(4102444800)})
        assert req.headers["Authorization"] == "tok"
        assert req.url.params["routeType"] == "drive"
        return httpx.Response(200, json=load("ntu_changi_drive.json"))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    om = OneMapRouting(OneMapAuth("a@b.c", "pw", http=http), http=http)
    r1 = om.route((1.348, 103.683), (1.364, 103.991), "drive", DEP)
    om.route((1.348, 103.683), (1.364, 103.991), "drive", DEP)
    assert r1.duration_s == float(load("ntu_changi_drive.json")["route_summary"]["total_time"])
    assert sum(c.url.path.endswith("getToken") for c in calls) == 1  # token reused


def test_onemap_unconfigured_is_skipped():
    om = OneMapRouting(OneMapAuth("", ""))
    assert not om.supports("drive")
    chain = FallbackRouting([om, StraightRouting()])
    assert chain.route((1.3, 103.7), (1.35, 103.8), "drive", DEP).provider == "fake"


def test_chain_error_message_for_transit():
    class NoTransit(StraightRouting):
        def supports(self, mode):
            return mode != "transit"

    with pytest.raises(ProviderError, match="OneMap credentials"):
        FallbackRouting([NoTransit()]).route((1.3, 103.7), (1.35, 103.8), "transit", DEP)


def test_cached_routing():
    inner = StraightRouting()
    c = CachedRouting(inner, TTLCache(None), 60)
    a = c.route((1.3, 103.7), (1.35, 103.8), "drive", DEP)
    b = c.route((1.3, 103.7), (1.35, 103.8), "drive", DEP)
    assert inner.calls == 1 and a == b
    c.duration_s((1.3, 103.7), (1.35, 103.8), "walk", DEP)
    c.duration_s((1.3, 103.7), (1.35, 103.8), "walk", DEP)
    assert inner.calls == 2


def test_failed_login_backs_off_and_falls_through():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req.url.path)
        return httpx.Response(400, json={"error": "Your password should be between 8 and 60 characters."})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    auth = OneMapAuth("a@b.c", "short-pw", http=http)
    om = OneMapRouting(auth, http=http)
    chain = FallbackRouting([om, StraightRouting()])
    # first call: OneMap login fails, chain falls through to the next provider
    assert chain.route((1.3, 103.7), (1.35, 103.8), "drive", DEP).provider == "fake"
    assert calls == ["/api/auth/post/getToken"]
    assert "at least 12 characters" in auth.last_error
    # while backing off: OneMap is skipped without touching the network
    assert not om.supports("drive")
    chain.route((1.3, 103.7), (1.36, 103.8), "drive", DEP)
    assert len(calls) == 1
    # transit has no other provider: the error says why
    with pytest.raises(ProviderError, match="OneMap login failed"):
        FallbackRouting([om]).route((1.3, 103.7), (1.35, 103.8), "transit", DEP)
    assert len(calls) == 1


def test_route_cache_does_not_shadow_recovered_primary():
    class Toggle(StraightRouting):
        name = "primary"
        on = False

        def supports(self, mode):
            return self.on

        def route(self, *a):
            r = super().route(*a)
            r.provider = "primary"
            return r

    p = Toggle()
    c = CachedRouting(FallbackRouting([p, StraightRouting()]), TTLCache(None), 600)
    assert c.route((1.3, 103.7), (1.35, 103.8), "drive", DEP).provider == "fake"
    p.on = True  # e.g. OneMap credentials fixed
    assert c.route((1.3, 103.7), (1.35, 103.8), "drive", DEP).provider == "primary"
