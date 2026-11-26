"""Opening hours at ETA (DESIGN §5.10). Returns True / False / "unknown"."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from opening_hours import OpeningHours, State


@lru_cache(maxsize=4096)
def _parse(expr: str):
    try:
        return OpeningHours(expr)
    except Exception:
        return None


def open_at(expr: str | None, when: datetime, tz: str = "Asia/Singapore"):
    if not expr:
        return "unknown"
    oh = _parse(expr.strip())
    if oh is None:
        return "unknown"
    local = when.astimezone(ZoneInfo(tz)).replace(tzinfo=None)
    try:
        state = oh.state(local)
    except Exception:
        return "unknown"
    if isinstance(state, tuple):
        state = state[0]
    if state == State.OPEN:
        return True
    if state == State.CLOSED:
        return False
    return "unknown"
