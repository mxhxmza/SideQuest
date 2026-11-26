"""Prayer times (DESIGN §5.9, D8): adhanpy, MUIS method, Shafi'i Asr default, Hanafi toggle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from adhanpy.calculation import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.PrayerTimes import PrayerTimes

PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
DISPLAY = {"fajr": "Subuh (Fajr)", "dhuhr": "Zohor (Dhuhr)", "asr": "Asar (Asr)",
           "maghrib": "Maghrib", "isha": "Isyak (Isha)"}


@dataclass(frozen=True)
class PrayerWindow:
    name: str
    start: datetime
    end: datetime  # start of the next prayer (Fajr ends at sunrise)


@lru_cache(maxsize=256)
def _day(lat: float, lng: float, d: date, asr: str, method: str, tz: str) -> dict[str, datetime]:
    try:
        m = CalculationMethod[method.upper()]
    except KeyError:
        m = CalculationMethod.SINGAPORE
    params = CalculationParameters(method=m)
    params.madhab = Madhab.HANAFI if asr == "hanafi" else Madhab.SHAFI
    p = PrayerTimes((lat, lng), datetime(d.year, d.month, d.day), calculation_parameters=params,
                    time_zone=ZoneInfo(tz))
    return {"fajr": p.fajr, "sunrise": p.sunrise, "dhuhr": p.dhuhr, "asr": p.asr,
            "maghrib": p.maghrib, "isha": p.isha}


def day_times(lat: float, lng: float, d: date, asr: str = "shafii", method: str = "SINGAPORE",
              tz: str = "Asia/Singapore") -> dict[str, datetime]:
    # round coordinates: SG varies ~2 min across the island; keeps the cache useful
    return dict(_day(round(lat, 2), round(lng, 2), d, asr, method, tz))


def windows(lat: float, lng: float, start: datetime, end: datetime, asr: str = "shafii",
            method: str = "SINGAPORE", tz: str = "Asia/Singapore") -> list[PrayerWindow]:
    """All prayer windows overlapping [start, end] (spanning days as needed)."""
    local = start.astimezone(ZoneInfo(tz))
    d0 = local.date() - timedelta(days=1)
    d1 = end.astimezone(ZoneInfo(tz)).date() + timedelta(days=1)
    out: list[PrayerWindow] = []
    d = d0
    while d <= d1:
        t = day_times(lat, lng, d, asr, method, tz)
        nxt = day_times(lat, lng, d + timedelta(days=1), asr, method, tz)
        ends = {"fajr": t["sunrise"], "dhuhr": t["asr"], "asr": t["maghrib"],
                "maghrib": t["isha"], "isha": nxt["fajr"]}
        for name in PRAYERS:
            w = PrayerWindow(name, t[name], ends[name])
            if w.end > start and w.start < end:
                out.append(w)
        d += timedelta(days=1)
    out.sort(key=lambda w: w.start)
    return out


def next_or_current(lat: float, lng: float, name: str, at: datetime, asr: str = "shafii",
                    method: str = "SINGAPORE", tz: str = "Asia/Singapore") -> PrayerWindow:
    """The window for `name` that is open at `at`, else the next one after `at`."""
    for w in windows(lat, lng, at - timedelta(hours=1), at + timedelta(days=2), asr, method, tz):
        if w.name == name and w.end > at:
            return w
    raise ValueError(f"no {name} window found")
