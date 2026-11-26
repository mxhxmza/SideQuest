"""Time windows -> route segments (DESIGN §5.2) and the shifting trip clock (§5.8)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from app.models import StopRequest

DEFAULT_TOLERANCE_MIN = 20.0
PRAYER_WINDOW_MIN = 60.0


class Clock:
    """Maps route time (seconds along the original geometry) <-> wall clock,
    accounting for delays (detour + dwell) inserted at chosen stops."""

    def __init__(self, depart: datetime):
        self.depart = depart
        self.events: list[tuple[float, float]] = []  # (route_t, delay_s)

    def copy(self) -> "Clock":
        c = Clock(self.depart)
        c.events = list(self.events)
        return c

    def add(self, route_t: float, delay_s: float) -> None:
        self.events.append((route_t, max(0.0, delay_s)))
        self.events.sort(key=lambda e: e[0])

    def set_delay(self, route_t: float, delay_s: float) -> None:
        """Change the delay of the stop at `route_t` (e.g. a shorter wait once
        earlier stops have pushed its ETA later)."""
        self.events = [(rt, max(0.0, delay_s) if abs(rt - route_t) < 1e-6 else d) for rt, d in self.events]

    def free_slot(self, route_t: float, step: float = 0.1) -> float:
        """A route time at/after `route_t` that no existing stop occupies, so two stops
        at the same point (e.g. both snapped to the route end) are sequenced, not overlapped."""
        while any(abs(rt - route_t) < step / 2 for rt, _ in self.events):
            route_t += step
        return route_t

    def delay_before(self, route_t: float) -> float:
        return sum(d for rt, d in self.events if rt < route_t - 1e-6)

    def at(self, route_t: float) -> datetime:
        return self.depart + timedelta(seconds=route_t + self.delay_before(route_t))

    def route_t_of(self, when: datetime) -> float:
        s = (when - self.depart).total_seconds()
        for rt, d in self.events:
            if s <= rt:
                break
            if s <= rt + d:
                return rt  # you're at that stop
            s -= d
        return s


@dataclass
class Window:
    start: datetime
    end: datetime
    target: Optional[datetime]
    prayer: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    # the stop can't be served before `start` (a prayer can't be prayed before its
    # time): arriving early means waiting there, and the whole [start, end] is fine
    hard_start: bool = False


_CLOCK_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*$")


def parse_hhmm(value) -> tuple[int, int]:
    m = _CLOCK_RE.match(str(value))
    if not m:
        raise ValueError(f"bad clock time {value!r}, expected HH:MM")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"bad clock time {value!r}")
    return h, mi


PrayerLookup = Callable[[str, datetime], tuple[datetime, datetime]]


def resolve_window(stop: StopRequest, depart: datetime, arrival: datetime,
                   prayer_lookup: PrayerLookup) -> Window:
    """Window in wall-clock time for a stop. `prayer_lookup(name, at)` returns
    the (start, end) of the prayer window open at / next after `at`."""
    w = stop.time_window
    tol = timedelta(minutes=w.tolerance_min if w.tolerance_min is not None else DEFAULT_TOLERANCE_MIN)
    if w.type == "any":
        return Window(depart, arrival, None)
    if w.type == "minutes_in":
        target = depart + timedelta(minutes=float(w.value or 0))
    elif w.type == "clock_time":
        h, mi = parse_hhmm(w.value)
        target = depart.replace(hour=h, minute=mi, second=0, microsecond=0)
        if target < depart - timedelta(hours=2):
            target += timedelta(days=1)
    elif w.type == "prayer":
        name = str(w.value or "").lower()
        p_start, p_end = prayer_lookup(name, depart)
        span = timedelta(minutes=w.tolerance_min if w.tolerance_min is not None else PRAYER_WINDOW_MIN)
        warnings: list[str] = []
        if w.relation == "before":
            start, end = p_start - span, p_start
            return Window(start, end, p_start - span / 2, prayer=name, warnings=warnings)
        start = p_start
        if p_start < depart:
            start = depart
            warnings.append(f"{name.title()} window is already open at departure")
        end = min(start + span, p_end)
        if w.until:
            h, mi = parse_hhmm(w.until)
            until = p_start.replace(hour=h, minute=mi, second=0, microsecond=0)
            if until <= p_start and until + timedelta(days=1) <= p_end:
                until += timedelta(days=1)  # e.g. Isyak until 1am
            if until <= start:
                warnings.append(f"'until {w.until}' is before {name.title()} starts "
                                f"({p_start.strftime('%H:%M')}); using {name.title()} + "
                                f"{int(span.total_seconds() // 60)} min")
            elif until > p_end:
                end = p_end
                warnings.append(f"{name.title()} time ends at {p_end.strftime('%H:%M')}")
            else:
                end = until
        return Window(start, end, start, prayer=name, warnings=warnings, hard_start=True)
    else:  # pragma: no cover
        return Window(depart, arrival, None)
    if w.relation == "before":
        return Window(target - 2 * tol, target, target - tol)
    if w.relation == "after":
        return Window(target, target + 2 * tol, target + tol)
    return Window(target - tol, target + tol, target)


def _edge_span(win: Window, duration_s: float) -> float:
    """Stretch searched when a window lies outside the trip: the first/last
    quarter of the route (10–20 min), never more than the window itself."""
    window_s = (win.end - win.start).total_seconds()
    return min(window_s, max(600.0, min(1200.0, 0.25 * duration_s)))


def window_to_route_range(win: Window, clock: Clock, duration_s: float,
                          lead_s: float = 0.0) -> tuple[float, float, list[str]]:
    """Route-time [t0, t1] for a wall-clock window, clipped; warns and clamps when
    the window lies outside the trip.

    `lead_s` starts the search that much earlier on the route: a place is reached
    some minutes after leaving the route, so leaving just before the window opens
    can still arrive inside it (e.g. hop off one station before Asr starts)."""
    warnings: list[str] = []
    t0 = clock.route_t_of(win.start)
    t1 = clock.route_t_of(win.end)
    if t1 < 0:
        warnings.append("Requested time is before departure — searching near the start of the route")
        return 0.0, min(duration_s, _edge_span(win, duration_s)), warnings
    if t0 > duration_s:
        warnings.append("Requested time is after arrival — searching near the end of the route")
        return max(0.0, duration_s - _edge_span(win, duration_s)), duration_s, warnings
    return max(0.0, t0 - lead_s), min(duration_s, max(t1, t0)), warnings
