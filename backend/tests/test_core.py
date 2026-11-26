from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core import deeplink, hours, prayer
from app.core.detour import estimate_detour_min, transit_detour_min
from app.core.geo import Projection, decode_polyline, encode_polyline, haversine_m
from app.core.scoring import category_evidence, dedupe, dietary_evidence, score
from app.core.segments import Clock, resolve_window, window_to_route_range
from app.core.tags import CATEGORIES, matches_filters, matches_name
from app.core.timeline import Timeline
from app.models import Route, RouteLeg, StopRequest, TimeWindow, TransitStop

TZ = ZoneInfo("Asia/Singapore")
PROJ = Projection(1.3521, 103.8198)


def straight_route(km=10.0, minutes=20.0, n=11):
    lng1 = 103.70 + km / 111.195
    coords = [(1.35, 103.70 + (lng1 - 103.70) * i / (n - 1)) for i in range(n)]
    return Route(legs=[RouteLeg(mode="DRIVE", coords=coords, duration_s=minutes * 60, distance_m=km * 1000)],
                 duration_s=minutes * 60, distance_m=km * 1000, mode="drive", provider="t")


# ------------------------------------------------------------------ geo --

def test_polyline_roundtrip():
    pts = [(1.34831, 103.68312), (1.35, 103.7), (1.36441, 103.99153)]
    out = decode_polyline(encode_polyline(pts))
    assert all(abs(a - b) < 1e-5 for p, q in zip(pts, out) for a, b in zip(p, q))


def test_known_polyline():
    # Google's documented example
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_projection_error_small():
    a, b = (1.30, 103.70), (1.40, 103.95)
    ax, ay = PROJ.to_xy(*a)
    bx, by = PROJ.to_xy(*b)
    planar = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    assert abs(planar - haversine_m(a, b)) / haversine_m(a, b) < 0.001  # D10: <0.1%


# ------------------------------------------------------------- timeline --

def test_timeline_interpolation():
    tl = Timeline(straight_route(10, 20), PROJ)
    assert tl.duration == pytest.approx(1200)
    lat, lng = tl.position_at(600)
    assert lng == pytest.approx(103.70 + 5 / 111.195, abs=1e-4)
    assert tl.time_at(0.25) == pytest.approx(300, rel=1e-3)
    assert tl.fraction_at_time(900) == pytest.approx(0.75, rel=1e-3)
    n = tl.nearest(1.35 + 500 / 111195, 103.70 + 2 / 111.195)
    assert n.dist_m == pytest.approx(500, rel=0.01)
    assert n.along_t == pytest.approx(240, rel=0.01)


def test_timeline_segment_restriction():
    tl = Timeline(straight_route(10, 20), PROJ)
    # a point near km 2, but only search the km 6-10 stretch → nearest is the stretch start
    n = tl.nearest(1.35, 103.70 + 2 / 111.195, 720, 1200)
    assert n.along_t >= 700
    assert n.dist_m == pytest.approx(4000, rel=0.05)


def test_transit_waiting_stays_inside_leg():
    walk = RouteLeg(mode="WALK", coords=[(1.35, 103.70), (1.35, 103.705)], duration_s=300, start_s=0, end_s=300)
    bus = RouteLeg(mode="BUS", coords=[(1.35, 103.705), (1.35, 103.75)], duration_s=600, start_s=600, end_s=1200,
                   stops=[TransitStop(name="A", lat=1.35, lng=103.705, t_s=600),
                          TransitStop(name="B", lat=1.35, lng=103.75, t_s=1200)])
    r = Route(legs=[walk, bus], duration_s=1200, distance_m=5000, mode="transit", provider="t")
    tl = Timeline(r, PROJ)
    # during the wait (300..600 s) you're standing at the bus stop
    assert tl.position_at(450)[1] == pytest.approx(103.705, abs=1e-6)
    assert tl.leg_mode_at_time(900) == "BUS"
    assert [h.name for h in tl.halts] == ["A", "B"]
    assert tl.walk_ranges() == [(0.0, 300.0)]


# ------------------------------------------------------------- segments --

def _stop(tw: TimeWindow, cat="meal") -> StopRequest:
    return StopRequest(id="s1", category=cat, time_window=tw)


def _lookup(name, at):
    t = {"dhuhr": (13, 0), "asr": (16, 20)}[name]
    s = at.replace(hour=t[0], minute=t[1], second=0, microsecond=0)
    return s, s + timedelta(hours=3)


def test_clock_shift_and_inverse():
    dep = datetime(2026, 11, 27, 12, 0, tzinfo=TZ)
    c = Clock(dep)
    c.add(600, 1800)  # 30-min stop at route t=10min
    assert c.at(300) == dep + timedelta(seconds=300)
    assert c.at(1200) == dep + timedelta(seconds=1200 + 1800)
    assert c.route_t_of(dep + timedelta(seconds=1200)) == 600  # still at the stop
    assert c.route_t_of(dep + timedelta(seconds=3000)) == pytest.approx(1200)


def test_resolve_windows():
    dep = datetime(2026, 11, 27, 12, 30, tzinfo=TZ)
    arr = dep + timedelta(hours=2)
    w = resolve_window(_stop(TimeWindow(type="clock_time", value="13:00")), dep, arr, _lookup)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == ("12:40", "13:20")
    w = resolve_window(_stop(TimeWindow(type="minutes_in", value=45)), dep, arr, _lookup)
    assert w.target == dep + timedelta(minutes=45)
    w = resolve_window(_stop(TimeWindow(type="prayer", value="asr"), "mosque"), dep, arr, _lookup)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == ("16:20", "17:20")
    w = resolve_window(_stop(TimeWindow(type="prayer", value="asr", relation="before")), dep, arr, _lookup)
    assert w.end.strftime("%H:%M") == "16:20"
    w = resolve_window(_stop(TimeWindow(type="any")), dep, arr, _lookup)
    assert w.target is None and w.end == arr


def test_prayer_already_open_at_departure():
    dep = datetime(2026, 11, 27, 13, 30, tzinfo=TZ)
    w = resolve_window(_stop(TimeWindow(type="prayer", value="dhuhr"), "mosque"), dep, dep + timedelta(hours=1), _lookup)
    assert w.start == dep and w.warnings


def test_prayer_until_sets_window_end():
    dep = datetime(2026, 11, 26, 15, 45, tzinfo=TZ)
    arr = dep + timedelta(hours=1)
    w = resolve_window(_stop(TimeWindow(type="prayer", value="asr", until="18:00"), "mosque"), dep, arr, _lookup)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == ("16:20", "18:00")
    assert w.hard_start and not w.warnings
    # past the end of Asr time: capped, with a note
    w = resolve_window(_stop(TimeWindow(type="prayer", value="asr", until="20:00"), "mosque"), dep, arr, _lookup)
    assert w.end.strftime("%H:%M") == "19:20" and w.warnings
    # before Asr starts: ignored (usual +60 min), with a note
    w = resolve_window(_stop(TimeWindow(type="prayer", value="asr", until="16:00"), "mosque"), dep, arr, _lookup)
    assert w.end.strftime("%H:%M") == "17:20" and w.warnings


def test_route_range_lead_starts_search_before_window():
    dep = datetime(2026, 11, 27, 12, 0, tzinfo=TZ)
    w = resolve_window(_stop(TimeWindow(type="prayer", value="dhuhr"), "mosque"), dep, dep + timedelta(hours=2),
                       _lookup)  # 13:00-14:00
    assert window_to_route_range(w, Clock(dep), 7200)[:2] == (3600, 7200)
    assert window_to_route_range(w, Clock(dep), 7200, lead_s=780)[:2] == (2820, 7200)


def test_window_outside_trip_clamps():
    dep = datetime(2026, 11, 27, 12, 30, tzinfo=TZ)
    c = Clock(dep)
    w = resolve_window(_stop(TimeWindow(type="clock_time", value="18:00")), dep, dep + timedelta(hours=1), _lookup)
    t0, t1, warn = window_to_route_range(w, c, 3600)
    assert warn and t1 == 3600 and t0 < t1


# ---------------------------------------------------------- detour/score --

def test_detour_estimate():
    # 1 km off route, drive 30 km/h, circuity 1.3 → 2*1000*1.3/500 = 5.2 min
    assert estimate_detour_min(1000, 30) == pytest.approx(5.2)
    assert transit_detour_min(400, 4.8, 5) == pytest.approx(2 * 400 * 1.3 / 80 + 5)


def test_dietary_evidence():
    ok, ev, weak = dietary_evidence({"diet:halal": "yes"}, ["halal"])
    assert ok and not weak and ev[0].strength == "strong"
    ok, ev, weak = dietary_evidence({"name": "Ali's Nasi Padang"}, ["halal"])
    assert ok and weak
    ok, ev, weak = dietary_evidence({"name": "McDonald's", "brand": "McDonald's"}, ["halal"])
    assert ok and weak and "verify" in ev[0].text
    assert dietary_evidence({"name": "Pork Ribs"}, ["halal"])[0] is False
    assert dietary_evidence({"diet:halal": "no", "name": "Halal-ish"}, ["halal"])[0] is False
    assert dietary_evidence({"diet:vegetarian": "only"}, ["vegetarian"])[0] is True
    assert dietary_evidence({}, [])[0] is True


def test_category_evidence_name_hint_requires_kind():
    cat = CATEGORIES["charger"]
    assert category_evidence(cat, {"shop": "electronics"})[0]
    assert category_evidence(cat, {"shop": "department_store", "name": "Courts"})[0]
    assert not category_evidence(cat, {"amenity": "food_court", "name": "Food Courts"})[0]
    assert category_evidence(CATEGORIES["prayer_room"], {"name": "Surau Al-Firdaus", "amenity": "place_of_worship",
                                                         "religion": "muslim"})[0]


def test_score_terms():
    s, b = score(4.0, False, True, None, 20, True, False)
    assert b["closed_at_eta"] == 60 and s == 64
    s, b = score(4.0, "unknown", True, 30, 20, False, True)
    assert b == {"detour": 4.0, "hours_unknown": 3.0, "outside_window": 5.0, "off_target": 2.0, "no_name": 2.0,
                 "weak_dietary_evidence": 5.0}
    s, b = score(4.0, True, True, 5, 20, True, False)
    assert b["off_target"] == 0.5  # tie-breaker inside the window
    s, b = score(1.0, True, True, None, 0, True, False, push_overflow_min=10)
    assert b["pushes_other_stops"] == 5.0
    s, b = score(4.0, True, True, 0, 20, True, False, combine_bonus=3)
    assert s == 1.0 and b["combine_bonus"] == -3


def test_dedupe_node_and_way():
    items = [("n1", "Masjid X", 1.35, 103.7, {"a": 1}), ("w2", "Masjid X", 1.35015, 103.7, {"a": 1, "b": 2}),
             ("n3", "Masjid X", 1.36, 103.7, {}), ("n3", "Dup id", 1.0, 103.0, {})]
    out = dedupe(items, key_latlng=lambda i: (i[2], i[3]), key_name=lambda i: i[1], key_osm=lambda i: i[0],
                 key_tags=lambda i: i[4])
    assert sorted(i[0] for i in out) == ["n3", "w2"]


# ----------------------------------------------------------- tags/hours --

def test_matches_filters_multivalue():
    f = CATEGORIES["meal"].filters
    assert matches_filters({"amenity": "cafe;restaurant"}, f)
    assert not matches_filters({"shop": "bakery"}, f)
    assert matches_name("Masjid Sultan", ("masjid",))
    assert not matches_name("Masjidxyz", ("masjid",))


def test_opening_hours():
    when = datetime(2026, 11, 27, 13, 0, tzinfo=TZ)  # Friday
    assert hours.open_at("Mo-Su 10:00-22:00", when) is True
    assert hours.open_at("Mo-Fr 08:00-12:00", when) is False
    assert hours.open_at(None, when) == "unknown"
    assert hours.open_at("not a valid expression ???", when) == "unknown"
    assert hours.open_at("24/7", when) is True


# --------------------------------------------------------------- prayer --

def test_prayer_times_singapore():
    t = prayer.day_times(1.3483, 103.6831, datetime(2026, 11, 26).date())
    assert t["fajr"].strftime("%H") == "05"
    assert "12:40" <= t["dhuhr"].strftime("%H:%M") <= "13:10"
    assert "16:00" <= t["asr"].strftime("%H:%M") <= "16:30"
    assert "18:45" <= t["maghrib"].strftime("%H:%M") <= "19:10"
    h = prayer.day_times(1.3483, 103.6831, datetime(2026, 11, 26).date(), asr="hanafi")
    assert h["asr"] > t["asr"]


def test_prayer_windows_span():
    s = datetime(2026, 11, 26, 12, 30, tzinfo=TZ)
    ws = prayer.windows(1.35, 103.8, s, s + timedelta(hours=7))
    assert [w.name for w in ws] == ["dhuhr", "asr", "maghrib"]
    assert ws[0].end == ws[1].start


# ------------------------------------------------------------- deeplink --

def test_deeplink():
    u = deeplink.gmaps_url((1.0, 103.0), (1.5, 104.0), [(1.1, 103.1), (1.2, 103.2)], "drive")
    assert u.startswith("https://www.google.com/maps/dir/?api=1")
    assert "waypoints=1.100000,103.100000|1.200000,103.200000" in u
    assert "travelmode=driving" in u
    t = deeplink.gmaps_url((1.0, 103.0), (1.5, 104.0), [(1.1, 103.1)], "transit")
    assert "waypoints" not in t and "travelmode=transit" in t
    legs = deeplink.leg_urls([("A", (1.0, 103.0)), ("B", (1.1, 103.1)), ("C", (1.2, 103.2))], "transit")
    assert [l for l, _ in legs] == ["A → B", "B → C"]


def test_clock_sequences_stops_at_the_same_point():
    dep = datetime(2026, 11, 27, 12, 0, tzinfo=TZ)
    c = Clock(dep)
    c.add(c.free_slot(1000.0), 20 * 60)   # mosque at the route end
    t2 = c.free_slot(1000.0)              # charger snapped to the same point
    assert t2 > 1000.0
    assert c.at(t2) == dep + timedelta(seconds=1000 + 20 * 60) + timedelta(seconds=t2 - 1000)
