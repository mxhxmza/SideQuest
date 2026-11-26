"""Shared prompt + JSON schema for LLM parsers. LLMs emit a category enum only (D3)."""
from __future__ import annotations

import json
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from app.core import tags as T
from app.core.segments import parse_hhmm
from app.models import ParseContext, StopConstraints, StopRequest, TimeWindow

Category = Literal[T.CATEGORY_KEYS]  # type: ignore[valid-type]
Dietary = Literal[T.DIETARY_KEYS]  # type: ignore[valid-type]

MEAL_WORDS = ("lunch", "dinner", "breakfast", "brunch", "supper")


class LLMWindow(BaseModel):
    type: Literal["minutes_in", "clock_time", "prayer", "any"] = "any"
    value: Optional[Union[float, str]] = None
    relation: Literal["at", "before", "after"] = "at"
    until: Optional[str] = None  # prayer only: latest time "HH:MM"


def _hhmm(v) -> Optional[str]:
    try:
        h, m = parse_hhmm(v)
    except ValueError:
        return None
    return f"{h:02d}:{m:02d}"


class LLMStop(BaseModel):
    query: str
    category: Category
    dietary: list[Dietary] = Field(default_factory=list)
    time_window: LLMWindow = Field(default_factory=LLMWindow)
    keywords: list[str] = Field(default_factory=list)  # only for category "keyword"


class LLMOutput(BaseModel):
    stops: list[LLMStop]


def json_schema() -> dict:
    return LLMOutput.model_json_schema()


def system_prompt() -> str:
    cats = "\n".join(f"- {k}: {c.label} (e.g. {', '.join(c.synonyms[:4])})" for k, c in T.CATEGORIES.items())
    return f"""You turn a traveller's free-text list of stops into JSON.
Return ONLY JSON matching: {{"stops": [{{"query": str, "category": one of the keys below,
"dietary": [subset of {list(T.DIETARY_KEYS)}], "time_window": {{"type": "minutes_in"|"clock_time"|"prayer"|"any",
"value": number|string|null, "relation": "at"|"before"|"after", "until": "HH:MM"|null}}}}]}}

Categories (use the key exactly; never invent new ones):
{cats}

Time window rules:
- "around 1pm" / "at 13:30" -> type clock_time, value "HH:MM" 24-hour ("13:00").
- "45 min in" / "after an hour" -> type minutes_in, value = minutes after departure (number).
- Islamic prayers -> type prayer, value one of fajr|dhuhr|asr|maghrib|isha
  (subuh=fajr, zohor/zuhur=dhuhr, asar=asr, isyak=isha). "before Maghrib" -> relation "before".
  A latest time for a prayer stop goes in "until" (24-hour): "asr anytime until 6pm" -> value "asr",
  until "18:00". Otherwise until is null.
- Meals without a time: lunch -> clock_time "12:30", breakfast "08:30", dinner "19:00".
- No time mentioned -> type any, value null.
- "pray"/"surau"/"musolla" without the word mosque -> prayer_room.
- Dietary words (halal, vegetarian, vegan) go in dietary, not in the category.
- If no category fits, use category "keyword" and put 1-2 short place-name search words in "keywords"
  (e.g. "buy durian" -> keywords ["durian"]). Never drop a requested stop.
One entry per requested stop, in the order given. "query" is the user's words for that stop."""


def to_stop_requests(out: LLMOutput) -> list[StopRequest]:
    res = []
    for i, s in enumerate(out.stops):
        w = s.time_window
        if w.type == "prayer" and isinstance(w.value, str):
            w.value = w.value.lower()
        if w.type == "minutes_in" and isinstance(w.value, str):
            w.value = float(w.value)
        if w.type == "any":
            w.value = None
        tol = None
        q = s.query.lower()
        if (w.type == "clock_time" and s.category in ("meal", "hawker", "cafe")
                and any(m in q for m in MEAL_WORDS) and not any(ch.isdigit() for ch in q) and "noon" not in q):
            tol = 60
        res.append(StopRequest(
            id=f"s{i + 1}", query=s.query, category=s.category,
            name_keywords=list(s.keywords) if s.category == "keyword" else [],
            time_window=TimeWindow(type=w.type, value=w.value, relation=w.relation, tolerance_min=tol,
                                   until=_hhmm(w.until) if w.type == "prayer" and w.until else None),
            constraints=StopConstraints(dietary=list(s.dietary) if T.get(s.category).kind in T.DIETARY_KINDS
                                        else [])))
    return res


def user_prompt(text: str, ctx: ParseContext) -> str:
    dep = ctx.departure_time.isoformat() if ctx.departure_time else "unknown"
    return json.dumps({"departure_time": dep, "text": text})


def extract_json(content: str) -> dict:
    content = content.strip()
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(content[start:end + 1])
