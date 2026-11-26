from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.planner import Planner
from app.models import Point, StopConstraints, StopRequest, TimeWindow, TripRequest
from app.providers.places.fake import FakePlaces
from app.regions import get_region
from tests.fakes import DEST, ORIGIN, StraightRouting, lng_at_km, make_places

TZ = ZoneInfo("Asia/Singapore")
DEP = datetime(2026, 11, 27, 12, 30, tzinfo=TZ)  # Friday


def stops():
    return [
        StopRequest(id="s1", query="halal lunch around 12:50", category="meal",
                    time_window=TimeWindow(type="clock_time", value="12:50"),
                    constraints=StopConstraints(dietary=["halal"])),
        StopRequest(id="s2", query="mosque at zohor", category="mosque",
                    time_window=TimeWindow(type="prayer", value="dhuhr")),
        StopRequest(id="s3", query="phone charger", category="charger"),
    ]


def trip(**kw):
    return TripRequest(origin=Point(lat=ORIGIN[0], lng=ORIGIN[1], name="A"),
                       destination=Point(lat=DEST[0], lng=DEST[1], name="B"),
                       mode=kw.pop("mode", "drive"), departure_time=DEP, stops=kw.pop("stops", stops()), **kw)


@pytest.fixture
def planner():
    return Planner(StraightRouting(), FakePlaces(make_places()), get_region("singapore"))


def by_id(plan, sid):
    return next(s for s in plan.stops if s.request.id == sid)


def test_plan_basic_ranking_and_evidence(planner):
    plan = planner.plan(trip())
    meal = by_id(plan, "s1")
    names = [c.name for c in meal.candidates]
    assert meal.chosen.name == "Nasi Lemak House"
    assert "Pork Ribs Place" not in names            # no halal evidence → excluded
    weak = next(c for c in meal.candidates if c.name == "Ali's Nasi Padang")
    assert weak.score_breakdown.get("weak_dietary_evidence") == 5
    closed = next(c for c in meal.candidates if c.name == "Closed Halal Cafe")
    assert closed.open_at_eta is False and closed.score_breakdown["closed_at_eta"] == 60
    assert meal.candidates[0].detour_exact is True   # top 3 get exact detours
    assert any(e.text == "OSM diet:halal=yes" for e in meal.chosen.evidence)


def test_combined_container_stop(planner):
    plan = planner.plan(trip())
    meal, charger = by_id(plan, "s1"), by_id(plan, "s3")
    assert meal.chosen.kind == "container"
    assert set(meal.chosen.matched_stop_ids) == {"s1", "s3"}
    assert "combine_bonus" in meal.chosen.score_breakdown
    assert charger.covered_by == "s1"
    assert charger.chosen.name == "Challenger" and charger.chosen.detour_min == 0
    assert charger.chosen.eta == meal.chosen.eta + timedelta(minutes=45)


def test_cascade_shifts_later_stops(planner):
    plan = planner.plan(trip())
    meal, mosque = by_id(plan, "s1"), by_id(plan, "s2")
    assert mosque.chosen.name == "Masjid Al-Test"
    # mosque is reached after lunch (45) + charger (15) dwell
    assert mosque.chosen.eta > meal.chosen.eta + timedelta(minutes=60)
    names = [c.name for c in mosque.candidates]
    assert names.count("Masjid Al-Test") == 1        # node+way duplicate removed
    assert "Masjid Far" not in names                 # outside the 2 km buffer
    base = planner.routing.route(ORIGIN, DEST, "drive", DEP).duration_s
    added = sum(s.added_min for s in plan.stops)
    dwell = 45 + 15 + 20
    expected = DEP + timedelta(seconds=base) + timedelta(minutes=added + dwell)
    assert abs((plan.arrival_eta - expected).total_seconds()) < 90


def test_prayer_rows_and_deeplink(planner):
    plan = planner.plan(trip())
    names = [p.name for p in plan.prayer_times]
    assert "dhuhr" in names
    dh = next(p for p in plan.prayer_times if p.name == "dhuhr")
    assert dh.stop_id == "s2" and 0 <= dh.route_fraction <= 1
    assert plan.gmaps_url.count("|") == 1            # two distinct waypoints: mall + mosque
    kinds = [r.kind for r in plan.timeline]
    assert kinds[0] == "depart" and kinds[-1] == "arrive"
    assert plan.timeline == sorted(plan.timeline, key=lambda r: r.time)


def test_pin_overrides_choice_and_combination(planner):
    plan = planner.plan(trip(pinned={"s1": "n6"}))
    meal, charger = by_id(plan, "s1"), by_id(plan, "s3")
    assert meal.chosen.osm_id == "n6"
    assert charger.covered_by is None and charger.chosen is not None
    # Challenger (km 12) would push the already-late mosque visit further; the
    # planner prefers a shop after the timed stops instead.
    assert charger.chosen.name == "Gadget Hut"
    assert "pushes_other_stops" in next(c for c in charger.candidates if c.name == "Challenger").score_breakdown


def test_no_matches_warns(planner):
    s = [StopRequest(id="s1", category="petrol")]
    plan = planner.plan(trip(stops=s))
    assert plan.stops[0].chosen is None
    assert any("No matching places" in w for w in plan.stops[0].warnings)


def test_transit_hop_off(planner):
    s = [StopRequest(id="s1", category="mosque")]
    plan = planner.plan(trip(mode="transit", stops=s))
    c = plan.stops[0].chosen
    assert c is not None and c.name == "Masjid Al-Test"
    assert plan.gmaps_leg_urls and "waypoints" not in plan.gmaps_url
    assert plan.route.legs and plan.route.legs[1].mode == "BUS"


def test_origin_outside_region_rejected(planner):
    from app.providers.base import ProviderError
    t = trip()
    t.origin = Point(lat=3.15, lng=101.7)  # Kuala Lumpur
    with pytest.raises(ProviderError):
        planner.plan(t)


def test_exact_detours_use_one_matrix_call_per_stop():
    from app.core.geo import haversine_m

    class MatrixRouting(StraightRouting):
        matrix_calls = 0

        def matrix_s(self, points, mode):
            MatrixRouting.matrix_calls += 1
            return [[haversine_m(a, b) / 10 for b in points] for a in points]

    r = MatrixRouting()
    pl = Planner(r, FakePlaces(make_places()), get_region("singapore"))
    plan = pl.plan(trip())
    assert r.calls == 1  # only the main route; exact detours came from matrices
    assert 1 <= MatrixRouting.matrix_calls <= len(plan.stops)
    assert all(c.detour_exact for c in by_id(plan, "s1").candidates[:3])


def test_two_stops_past_route_end_are_sequenced_before_arrival():
    # both places lie beyond the destination, so both snap to the route's last point
    from app.models import Place
    places = [
        Place(id=50, osm_id="n50", name="End Mosque", lat=DEST[0] + 0.004, lng=DEST[1] + 0.004,
              tags={"amenity": "place_of_worship", "religion": "muslim", "name": "End Mosque"}),
        Place(id=51, osm_id="n51", name="End Gadgets", lat=DEST[0] - 0.004, lng=DEST[1] + 0.004,
              tags={"shop": "electronics", "name": "End Gadgets"}),
    ]
    pl = Planner(StraightRouting(), FakePlaces(places), get_region("singapore"))
    s = [StopRequest(id="s1", category="mosque", time_window=TimeWindow(type="clock_time", value="23:00")),
         StopRequest(id="s2", category="charger", time_window=TimeWindow(type="clock_time", value="23:30"))]
    plan = pl.plan(trip(stops=s))
    a, b = by_id(plan, "s1").chosen, by_id(plan, "s2").chosen
    assert (a.name, b.name) == ("End Mosque", "End Gadgets")
    assert b.eta >= a.eta + timedelta(minutes=20)      # charger after the mosque's 20-min stay
    assert plan.arrival_eta >= b.eta
    assert plan.timeline[-1].kind == "arrive"


def test_keyword_stop_searches_names():
    from app.core.planner import normalize_stop
    from app.models import Place
    places = make_places() + [Place(id=60, osm_id="n60", name="Durian King", lat=ORIGIN[0] + 0.001,
                                    lng=lng_at_km(10), tags={"shop": "greengrocer", "name": "Durian King"})]
    pl = Planner(StraightRouting(), FakePlaces(places), get_region("singapore"))
    s = normalize_stop(StopRequest(id="s1", category="keyword", name_keywords=["Durian"]))
    assert s.name_keywords == ["durian"] and s.label == "Durian"
    plan = pl.plan(trip(stops=[s]))
    c = plan.stops[0].chosen
    assert c.name == "Durian King" and c.evidence[0].strength == "weak"


def test_dietary_fallback_shows_unverified_options_with_warning():
    from app.models import Place
    places = make_places() + [Place(id=61, osm_id="n61", name="Gelato Corner", lat=ORIGIN[0] + 0.001,
                                    lng=lng_at_km(15), tags={"amenity": "ice_cream", "name": "Gelato Corner"})]
    pl = Planner(StraightRouting(), FakePlaces(places), get_region("singapore"))
    s = StopRequest(id="s1", category="ice_cream", constraints=StopConstraints(dietary=["halal"]))
    sp = pl.plan(trip(stops=[s])).stops[0]
    assert sp.chosen.name == "Gelato Corner"
    assert any("no halal evidence" in e.text for e in sp.chosen.evidence)
    assert any("unverified" in w for w in sp.warnings)
    # an evidenced option, when present, is the only kind shown (no fallback)
    places.append(Place(id=62, osm_id="n62", name="Halal Scoops", lat=ORIGIN[0] + 0.002, lng=lng_at_km(20),
                        tags={"amenity": "ice_cream", "diet:halal": "yes", "name": "Halal Scoops"}))
    sp = Planner(StraightRouting(), FakePlaces(places), get_region("singapore")).plan(trip(stops=[s])).stops[0]
    assert [c.name for c in sp.candidates] == ["Halal Scoops"] and not sp.warnings


def _passing_before_dhuhr(minutes_early: float) -> datetime:
    """Departure at which the fake drive (36 km/h) passes the mosque at km 25
    `minutes_early` minutes before Dhuhr starts."""
    from app.core import prayer
    dhuhr = prayer.day_times(ORIGIN[0], ORIGIN[1], DEP.date())["dhuhr"]
    return dhuhr - timedelta(hours=25 / 36) - timedelta(minutes=minutes_early)


def test_prayer_stop_reached_before_prayer_time_counts_the_wait(planner):
    dep = _passing_before_dhuhr(4)
    s = [StopRequest(id="s1", category="mosque", time_window=TimeWindow(type="prayer", value="dhuhr"))]
    plan = planner.plan(_trip_at(dep, s))
    sp = plan.stops[0]
    assert sp.chosen is not None and sp.chosen.name == "Masjid Al-Test"
    # you arrive before Dhuhr starts and wait there; the wait is real added time
    assert 3 <= sp.chosen.wait_min <= 4.5
    assert sp.chosen.score_breakdown["wait"] == pytest.approx(sp.chosen.wait_min, abs=0.1)
    assert sp.added_min == pytest.approx(sp.chosen.detour_min + sp.chosen.wait_min, abs=0.1)
    base = planner.routing.route(ORIGIN, DEST, "drive", dep).duration_s
    expected = dep + timedelta(seconds=base) + timedelta(minutes=sp.added_min + 20)
    assert abs((plan.arrival_eta - expected).total_seconds()) < 60


def test_prayer_wait_shrinks_when_an_earlier_stop_delays_arrival(planner):
    dep = _passing_before_dhuhr(4)
    s = [StopRequest(id="s1", category="mosque", time_window=TimeWindow(type="prayer", value="dhuhr")),
         StopRequest(id="s2", category="charger")]  # Challenger (km 12) is before the mosque
    plan = planner.plan(_trip_at(dep, s))
    mosque, charger = by_id(plan, "s1"), by_id(plan, "s2")
    assert charger.chosen.name == "Challenger"
    # 15 min of shopping earlier on the route: no more waiting for Dhuhr
    assert mosque.chosen.wait_min == 0 and mosque.added_min == mosque.chosen.detour_min
    assert "wait" not in mosque.chosen.score_breakdown
    base = planner.routing.route(ORIGIN, DEST, "drive", dep).duration_s
    added = sum(sp.added_min for sp in plan.stops)
    expected = dep + timedelta(seconds=base) + timedelta(minutes=added + 20 + 15)
    assert abs((plan.arrival_eta - expected).total_seconds()) < 60


def _trip_at(dep: datetime, s: list[StopRequest], mode: str = "drive") -> TripRequest:
    t = trip(stops=s, mode=mode)
    t.departure_time = dep
    return t


def test_transit_mosque_at_station_just_before_prayer_time(planner):
    """Regression (640860 → Matrix, Asr): the search started at the station the train
    reaches when Asr begins, so the mosque a short walk from the previous station —
    reached after Asr has started — was never offered: "no mosque along the way"."""
    from app.core import prayer
    from app.core.timeline import Timeline
    mosque = next(p for p in make_places() if p.name == "Masjid Al-Test")
    tl = Timeline(planner.routing.route(ORIGIN, DEST, "transit", DEP), planner.proj)
    mx, my = planner.proj.to_xy(mosque.lat, mosque.lng)
    halt = min(tl.halts, key=lambda h: (h.x - mx) ** 2 + (h.y - my) ** 2)
    nxt = next(h for h in tl.halts if h.t > halt.t)
    assert ((nxt.x - mx) ** 2 + (nxt.y - my) ** 2) ** 0.5 > 800  # next stop is too far to walk
    dhuhr = prayer.day_times(ORIGIN[0], ORIGIN[1], DEP.date())["dhuhr"]
    dep = dhuhr - timedelta(seconds=halt.t) - timedelta(minutes=3)  # bus leaves that stop 3 min before Dhuhr
    s = [StopRequest(id="s1", category="mosque", time_window=TimeWindow(type="prayer", value="dhuhr"))]
    sp = planner.plan(_trip_at(dep, s, mode="transit")).stops[0]
    assert sp.chosen is not None and sp.chosen.name == "Masjid Al-Test"
    assert sp.chosen.hop_off == halt.name
    assert sp.chosen.eta >= dhuhr and sp.chosen.wait_min == 0  # the walk gets you there after Dhuhr starts


def test_dietary_fallback_ignores_evidenced_places_out_of_reach():
    """Regression (halal cake, transit): a halal-tagged bakery 3 km from every station sat
    inside the search bbox, which suppressed the D16 fallback; the distance check then
    dropped it too, leaving "No matching places" despite bakeries next to the route."""
    from app.models import Place
    a, b = (1.30, 103.70), (1.40, 103.80)  # diagonal: the bbox corners are far from the route
    places = [Place(id=1, osm_id="n1", name="Far Halal Bakes", lat=1.301, lng=103.799,
                    tags={"shop": "bakery", "diet:halal": "yes", "name": "Far Halal Bakes"}),
              Place(id=2, osm_id="n2", name="Route Bakery", lat=1.351, lng=103.75,
                    tags={"shop": "bakery", "name": "Route Bakery"})]
    pl = Planner(StraightRouting(), FakePlaces(places), get_region("singapore"))
    s = StopRequest(id="s1", category="bakery", constraints=StopConstraints(dietary=["halal"]))
    t = TripRequest(origin=Point(lat=a[0], lng=a[1]), destination=Point(lat=b[0], lng=b[1]), mode="drive",
                    departure_time=DEP, stops=[s])
    sp = pl.plan(t).stops[0]
    assert [c.name for c in sp.candidates] == ["Route Bakery"]
    assert any("no halal evidence" in e.text for e in sp.chosen.evidence)
    assert any("unverified" in w for w in sp.warnings)
