"""Rule-based NL parser (default backend, DESIGN §6).

clauses (split on , ; and then) → keyword lexicon → category, dietary + cuisine lexicons,
time regexes ("around 1pm", "at 13:30", "45 min in", "after an hour", "at Asr",
"before Maghrib").
"""
from __future__ import annotations

import re
from typing import Optional

from app.core import tags as T
from app.models import ParseContext, StopConstraints, StopRequest, TimeWindow

PRAYER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "fajr": ("subuh", "suboh", "fajr", "fajar", "subh", "suboh"),
    "dhuhr": ("zohor", "zuhur", "zuhr", "dhuhr", "duhr", "zohr", "dzuhur", "zuhor", "dhuhur", "luhur"),
    "asr": ("asar", "asr", "ashar", "assar"),
    "maghrib": ("maghrib", "magrib", "maghreb"),
    "isha": ("isyak", "isya", "isha", "ishaa", "esha", "isyak"),
}
_PRAYER_LOOKUP = {syn: name for name, syns in PRAYER_SYNONYMS.items() for syn in syns}
_PRAYER_ALT = "|".join(sorted(_PRAYER_LOOKUP, key=len, reverse=True))

MEAL_DEFAULT_TIMES = {"breakfast": "08:30", "brunch": "11:00", "lunch": "12:30", "dinner": "19:00",
                      "supper": "21:30"}

NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10,
             "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "sixty": 60,
             "half an": 0.5, "half a": 0.5}
_NUM = r"(\d+(?:\.\d+)?|half an?|an?|one|two|three|four|five|ten|fifteen|twenty|thirty|forty-five|forty|sixty)"
_UNIT = r"(minutes?|mins?|m|hours?|hrs?|h)"

_SPLIT = re.compile(r"\s*(?:[,;\n]|\bthen\b|\band then\b|\bafter that\b|\balso\b|\bplus\b|\band\b)\s*", re.I)

RE_PRAYER = re.compile(
    rf"\b(?P<rel>at|near|around|for|during|after|before|by|when)?\s*(?:the\s+)?(?P<p>{_PRAYER_ALT})\b"
    r"(?:\s+(?:time|prayers?|solat|salah))?", re.I)
RE_MIN_IN = re.compile(rf"\b{_NUM}\s*{_UNIT}\s+(?:in|into)\b", re.I)
RE_AFTER = re.compile(rf"\b(?:after|in|within)\s+(?:about\s+|around\s+)?{_NUM}\s*{_UNIT}\b", re.I)
RE_HALFWAY = re.compile(r"\bhalf\s*way\b|\bmidway\b", re.I)
RE_CLOCK_AMPM = re.compile(
    r"\b(?P<rel>around|about|at|by|before|after|approx\.?|approximately)?\s*~?\s*"
    r"(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>am|pm|a\.m\.|p\.m\.)", re.I)
RE_CLOCK_24 = re.compile(r"\b(?P<rel>around|about|at|by|before|after)?\s*~?\s*(?P<h>[01]?\d|2[0-3])[:.](?P<m>[0-5]\d)\b(?!\s*(?:am|pm))", re.I)
RE_NOON = re.compile(r"\b(?P<rel>around|about|at|by|before|after)?\s*(?P<w>noon|midday|midnight)\b", re.I)
# latest time for a prayer stop: "asr anytime until 6pm", "zohor before 2:30pm", "by 18:00"
RE_UNTIL = re.compile(
    r"\b(?:until|till|til|up\s*to|upto|by|before|no\s+later\s+than)\s+(?P<h>\d{1,2})"
    r"(?:(?:[:.](?P<m>\d{2}))?\s*(?P<ap>am|pm|a\.m\.|p\.m\.)|[:.](?P<m24>\d{2}))", re.I)


def _num(s: str) -> float:
    s = s.lower()
    if s in NUM_WORDS:
        return NUM_WORDS[s]
    return float(s)


def _minutes(n: str, unit: str) -> float:
    v = _num(n)
    return v * 60 if unit.lower().startswith("h") else v


def _rel(word: Optional[str]) -> str:
    w = (word or "").lower()
    if w in ("before", "by"):
        return "before"
    if w == "after":
        return "after"
    return "at"


def _find_phrase(text: str, phrases) -> Optional[tuple[str, int]]:
    best = None
    for ph in phrases:
        m = re.search(r"(?<![a-z])" + re.escape(ph) + r"(?![a-z])", text)
        if m and (best is None or len(ph) > len(best[0])):
            best = (ph, m.start())
    return best


def detect_category(clause: str) -> Optional[str]:
    best: Optional[tuple[int, str]] = None
    for key, cat in T.CATEGORIES.items():
        hit = _find_phrase(clause, cat.synonyms + tuple(cat.name_keywords))
        if hit and (best is None or len(hit[0]) > best[0]):
            best = (len(hit[0]), key)
    return best[1] if best else None


def detect_dietary(clause: str) -> list[str]:
    out = []
    for key, syns in T.DIETARY_SYNONYMS.items():
        if _find_phrase(clause, syns):
            out.append(key)
    if "vegan" in out and "vegetarian" in out:
        out.remove("vegetarian")
    return out


def detect_cuisine(clause: str) -> list[str]:
    """Cuisines mentioned in a clause ("italian", "sushi" → japanese)."""
    return [key for key, cd in T.CUISINES.items() if _find_phrase(clause, cd.synonyms)]


def _is_food(cat: Optional[str]) -> bool:
    return cat is not None and T.get(cat).kind in T.CUISINE_KINDS


def _until(clause: str) -> Optional[str]:
    m = RE_UNTIL.search(clause)
    if not m:
        return None
    h = int(m.group("h"))
    if m.group("ap"):
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if m.group("ap").lower().startswith("p") else 0)
        mi = int(m.group("m") or 0)
    else:
        mi = int(m.group("m24"))
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def detect_window(clause: str, category: Optional[str]) -> TimeWindow:
    m = RE_PRAYER.search(clause)
    if m:
        rel = _rel(m.group("rel"))
        return TimeWindow(type="prayer", value=_PRAYER_LOOKUP[m.group("p").lower()], relation=rel,
                          until=_until(clause) if rel != "before" else None)
    m = RE_CLOCK_AMPM.search(clause)
    if m:
        h = int(m.group("h")) % 12
        if m.group("ap").lower().startswith("p"):
            h += 12
        mi = int(m.group("m") or 0)
        return TimeWindow(type="clock_time", value=f"{h:02d}:{mi:02d}", relation=_rel(m.group("rel")))
    m = RE_CLOCK_24.search(clause)
    if m:
        return TimeWindow(type="clock_time", value=f"{int(m.group('h')):02d}:{m.group('m')}",
                          relation=_rel(m.group("rel")))
    m = RE_NOON.search(clause)
    if m:
        v = "00:00" if m.group("w").lower() == "midnight" else "12:00"
        return TimeWindow(type="clock_time", value=v, relation=_rel(m.group("rel")))
    m = RE_MIN_IN.search(clause)
    if m:
        return TimeWindow(type="minutes_in", value=_minutes(m.group(1), m.group(2)))
    m = RE_AFTER.search(clause)
    if m:
        return TimeWindow(type="minutes_in", value=_minutes(m.group(1), m.group(2)))
    for meal, t in MEAL_DEFAULT_TIMES.items():
        if _find_phrase(clause, (meal,)) and category in ("meal", "hawker", "cafe"):
            return TimeWindow(type="clock_time", value=t, tolerance_min=60)
    return TimeWindow(type="any")


def split_clauses(text: str) -> list[str]:
    parts = [p.strip(" .!?") for p in _SPLIT.split(text or "")]
    return [p for p in parts if p]


# Words that carry no "what" — stripped before deciding a clause is a real request.
STOPWORDS = set("""
a an the some any my our me i we us you it this that these those of to for from in on at by with and or
also then plus please pls want wanna need needs would like love get got grab pick picks up buy buying
purchase find look looking go going stop stops stopping visit quick quickly maybe somewhere something
anything anywhere place places spot spots shop shops store stores outlet one ones along way route trip
journey en near nearby around close closest good nice cheap best decent before after during time times
minute minutes mins min hour hours am pm let lets have eat eating get some kind sort few bit little
anytime whenever until till til upto latest later than
hmm hm um uh erm ok okay whatever thanks thank yes no so just really very too lol idk anyway etc
""".split())


def content_words(clause: str) -> list[str]:
    """Words left once time expressions, prayer names, dietary/cuisine words and filler are removed."""
    low = clause.lower()
    for rx in (RE_PRAYER, RE_CLOCK_AMPM, RE_CLOCK_24, RE_NOON, RE_MIN_IN, RE_AFTER, RE_HALFWAY):
        low = rx.sub(" ", low)
    for syns in [*T.DIETARY_SYNONYMS.values(), *(c.synonyms for c in T.CUISINES.values())]:
        for syn in syns:
            low = re.sub(r"(?<![a-z])" + re.escape(syn) + r"(?![a-z])", " ", low)
    words = re.findall(r"[a-z0-9][a-z0-9'&-]*", low)
    return [w for w in words if w not in STOPWORDS and w not in _PRAYER_LOOKUP and not w.isdigit()]


def _merge_fragments(clauses: list[str]) -> list[str]:
    """Re-attach pure modifiers (e.g. 'halal' or 'around 1pm') to the previous clause:
    'lunch, halal, around 1pm'. A clause with real content of its own is never merged —
    that used to swallow requests the lexicon didn't know (e.g. 'halal ... ice cream').
    A cuisine ('pizza') only merges into a food clause; after 'petrol' it is its own stop."""
    out: list[str] = []
    for c in clauses:
        low = c.lower()
        has_cat = detect_category(low) is not None
        has_prayer = RE_PRAYER.search(low) is not None
        prev_cat = detect_category(out[-1].lower()) if out else None
        cuisine_ok = not detect_cuisine(low) or (
            bool(out) and (_is_food(prev_cat) or (prev_cat is None and bool(detect_cuisine(out[-1].lower())))))
        if out and not has_cat and not has_prayer and not content_words(low) and cuisine_ok:
            out[-1] = out[-1] + " " + c
        else:
            out.append(c)
    return out


def keyword_phrase(words: list[str]) -> list[str]:
    """Name-search keywords from leftover content words: the phrase, plus its longer words."""
    phrase = " ".join(words[:3])
    extra = [w for w in words[:3] if len(w) >= 5 and w != phrase]
    return [phrase] + extra


class RulesParser:
    name = "rules"

    def parse(self, text: str, ctx: ParseContext) -> list[StopRequest]:
        return self.parse_with_notes(text, ctx)[0]

    def parse_with_notes(self, text: str, ctx: ParseContext) -> tuple[list[StopRequest], list[str]]:
        """Stops, plus the clauses that could not be turned into a stop."""
        stops: list[StopRequest] = []
        unrecognized: list[str] = []
        for clause in _merge_fragments(split_clauses(text)):
            low = clause.lower()
            cat = detect_category(low)
            diet = detect_dietary(low)
            cuisine = detect_cuisine(low)
            keywords: list[str] = []
            label = None
            if cat is None and RE_PRAYER.search(low):
                cat = "prayer_room"
            if cat is None and cuisine:
                cat = "meal"  # "pizza", "something japanese"
            if cat is None:
                words = content_words(low)
                if words:
                    # unknown thing: search place names for it rather than dropping it
                    cat = "keyword"
                    keywords = keyword_phrase(words)
                    label = keywords[0].title()
                elif diet:
                    cat = "meal"
            if cat is None:
                unrecognized.append(clause)
                continue
            win = detect_window(low, cat)
            stops.append(StopRequest(
                id=f"s{len(stops) + 1}", query=clause, category=cat, name_keywords=keywords, label=label,
                time_window=win,
                constraints=StopConstraints(dietary=diet if T.get(cat).kind in T.DIETARY_KINDS else [],
                                            cuisine=cuisine if T.get(cat).kind in T.CUISINE_KINDS else []),
            ))
        return stops, unrecognized
