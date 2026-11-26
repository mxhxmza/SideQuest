import json
from pathlib import Path

import pytest

from app.models import ParseContext
from app.providers.llm.rules import RulesParser, split_clauses

P = RulesParser()
CTX = ParseContext()


def parse(t):
    return P.parse(t, CTX)


def test_spec_example():
    s = parse("halal lunch around 1pm, a mosque near Asr time, somewhere to buy a phone charger")
    assert [x.category for x in s] == ["meal", "mosque", "charger"]
    assert s[0].constraints.dietary == ["halal"]
    assert (s[0].time_window.type, s[0].time_window.value) == ("clock_time", "13:00")
    assert (s[1].time_window.type, s[1].time_window.value) == ("prayer", "asr")
    assert s[2].time_window.type == "any"


@pytest.mark.parametrize("text,cat,wtype,value", [
    ("coffee 45 min in", "cafe", "minutes_in", 45),
    ("toilet after an hour", "toilet", "minutes_in", 60),
    ("ATM in 1.5 hours", "atm", "minutes_in", 90),
    ("pray zohor", "prayer_room", "prayer", "dhuhr"),
    ("surau before maghrib", "prayer_room", "prayer", "maghrib"),
    ("dinner at 19:30", "meal", "clock_time", "19:30"),
    ("petrol at 7.15pm", "petrol", "clock_time", "19:15"),
    ("lunch", "meal", "clock_time", "12:30"),
    ("isyak at a mosque", "mosque", "prayer", "isha"),
    ("charge my car", "ev_charging", "any", None),
])
def test_cases(text, cat, wtype, value):
    s = parse(text)
    assert len(s) == 1
    assert s[0].category == cat
    assert s[0].time_window.type == wtype
    if value is not None:
        assert s[0].time_window.value == value


def test_relation_before():
    s = parse("supermarket before 6pm")
    assert s[0].time_window.relation == "before"


def test_fragments_are_merged():
    s = parse("lunch, halal, around 1pm")
    assert len(s) == 1 and s[0].constraints.dietary == ["halal"] and s[0].time_window.value == "13:00"


def test_split():
    assert split_clauses("a, b; c then d and e") == ["a", "b", "c", "d", "e"]


def test_unknown_is_dropped():
    assert parse("hmm whatever") == []


def test_eval_cases_rules_accuracy():
    """The committed eval set must stay above a floor for the default backend."""
    path = Path(__file__).resolve().parents[1] / "eval" / "cases.jsonl"
    cases = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(cases) >= 20
    exact = 0
    for c in cases:
        got = [{"category": s.category, "dietary": sorted(s.constraints.dietary), "type": s.time_window.type,
                "value": s.time_window.value} for s in parse(c["text"])]
        exp = [{"category": e["category"], "dietary": sorted(e.get("dietary", [])), "type": e["window"]["type"],
                "value": e["window"].get("value")} for e in c["expected"]]
        exact += got == exp
    assert exact / len(cases) >= 0.8


def test_user_example_mosque_and_halal_ice_cream():
    s = parse("mosque to pray asr, some halal shop to buy ice cream along the way")
    assert [(x.category, x.constraints.dietary, x.time_window.type) for x in s] == [
        ("mosque", [], "prayer"), ("ice_cream", ["halal"], "any")]
    assert s[0].time_window.value == "asr"


def test_unknown_things_become_name_search_not_dropped():
    s = parse("need to buy durian and a car wash")
    assert [x.category for x in s] == ["keyword", "keyword"]
    assert s[0].name_keywords == ["durian"] and s[1].name_keywords[0] == "car wash"


def test_content_clause_is_not_merged_into_previous():
    s = parse("mosque at asr, halal durian")
    assert len(s) == 2 and s[1].category == "keyword" and s[1].constraints.dietary == ["halal"]


def test_parse_with_notes_reports_leftovers():
    from app.providers.llm.rules import RulesParser
    stops, unrecognized = RulesParser().parse_with_notes("toilet, hmm whatever", CTX)
    assert [x.category for x in stops] == ["toilet"]
    # pure filler merges into the previous clause rather than becoming a stop
    assert unrecognized == []
    stops, unrecognized = RulesParser().parse_with_notes("hmm whatever", CTX)
    assert stops == [] and unrecognized == ["hmm whatever"]


def test_user_example_mosque_until_and_halal_cake():
    s = parse("mosque to pray asr anytime until 6 pm, some halal shop to buy  cake along the way")
    assert [(x.category, x.constraints.dietary) for x in s] == [("mosque", []), ("bakery", ["halal"])]
    w = s[0].time_window
    assert (w.type, w.value, w.relation, w.until) == ("prayer", "asr", "at", "18:00")
    assert s[1].time_window.type == "any"


@pytest.mark.parametrize("text,value,until", [
    ("mosque at asr, anytime until 6pm", "asr", "18:00"),   # modifier clause merges into the stop
    ("zohor before 2:30pm", "dhuhr", "14:30"),
    ("surau for isyak till 23:30", "isha", "23:30"),
    ("pray asr by 5.45 pm", "asr", "17:45"),
    ("mosque before maghrib", "maghrib", None),            # 'before <prayer>' is a relation, not an end time
    ("mosque at asr", "asr", None),
])
def test_prayer_until(text, value, until):
    s = parse(text)
    assert len(s) == 1
    assert (s[0].time_window.type, s[0].time_window.value, s[0].time_window.until) == ("prayer", value, until)


def test_worship_and_cuisine_requests_for_everyone():
    from datetime import datetime, timedelta, timezone
    from app.models import ParseContext
    from app.providers.llm.rules import RulesParser
    ctx = ParseContext(departure_time=datetime(2026, 11, 26, 15, 55, tzinfo=timezone(timedelta(hours=8))))
    got = lambda t: [(s.category, s.constraints.dietary, s.constraints.cuisine) for s in RulesParser().parse(t, ctx)]
    assert got("church before 10am, then Italian dinner") == [("church", [], []), ("meal", [], ["italian"])]
    assert got("Hindu temple and a vegetarian lunch") == [("hindu_temple", [], []), ("meal", ["vegetarian"], [])]
    assert got("buddhist temple, gurdwara, synagogue") == [("buddhist_temple", [], []), ("gurdwara", [], []),
                                                           ("synagogue", [], [])]
    assert got("chinese temple then dim sum") == [("taoist_temple", [], []), ("meal", [], ["chinese"])]
    # a bare cuisine is a food stop; it merges only into a food clause
    assert got("petrol, pizza") == [("petrol", [], []), ("meal", [], ["pizza"])]
    assert got("dinner at 7pm, japanese") == [("meal", [], ["japanese"])]
    assert got("mosque at Asr, then a halal restaurant") == [("mosque", [], []), ("meal", ["halal"], [])]


# The landing page's "Ask for anything" chips (frontend/src/components/landing/AskAnything.tsx)
LANDING_CHIPS = [
    ("church before 10am", "church", None), ("Hindu temple", "hindu_temple", None),
    ("Buddhist temple", "buddhist_temple", None), ("Chinese temple", "taoist_temple", None),
    ("mosque at Asr", "mosque", None), ("surau", "prayer_room", None), ("gurdwara", "gurdwara", None),
    ("synagogue", "synagogue", None), ("temple", "temple", None),
    ("Italian dinner", "meal", "italian"), ("pizza", "meal", "pizza"), ("sushi", "meal", "japanese"),
    ("dim sum", "meal", "chinese"),
    ("Indian lunch", "meal", "indian"), ("Korean BBQ", "meal", "korean"), ("Thai food", "meal", "thai"),
    ("pho", "meal", "vietnamese"), ("nasi padang", "meal", "malay"), ("chicken rice", "meal", "local"),
    ("burger", "meal", "western"), ("French bistro", "meal", "french"), ("tacos", "meal", "mexican"),
    ("kebab", "meal", "middle_eastern"), ("seafood dinner", "meal", "seafood"), ("tapas", "meal", "spanish"),
    ("bubble tea", "cafe", None), ("7-eleven", "convenience", None), ("groceries", "supermarket", None),
    ("flowers", "florist", None), ("durian", "keyword", None), ("bike shop", "keyword", None),
]


@pytest.mark.parametrize("text,category,cuisine", LANDING_CHIPS)
def test_landing_page_chips_parse(text, category, cuisine):
    from datetime import datetime, timedelta, timezone
    from app.models import ParseContext
    from app.providers.llm.rules import RulesParser
    ctx = ParseContext(departure_time=datetime(2026, 11, 26, 15, 55, tzinfo=timezone(timedelta(hours=8))))
    (s,) = RulesParser().parse(text, ctx)
    assert s.category == category and s.constraints.cuisine == ([cuisine] if cuisine else [])
