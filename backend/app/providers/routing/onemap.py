"""OneMap (SLA) routing — primary provider for Singapore, incl. public transport.

Token: POST /api/auth/post/getToken {email, password} -> {access_token, expiry_timestamp}
(~3-day JWT). Refreshed automatically an hour before expiry. Credentials stay server-side.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

import httpx

from app.cache import TokenBucket
from app.core.geo import decode_polyline
from app.models import Mode, Route, RouteLeg, TransitStop
from app.providers.base import LatLng, ProviderError
from app.providers.http import client

BASE = "https://www.onemap.gov.sg"
ROUTE_TYPE = {"drive": "drive", "walk": "walk", "cycle": "cycle", "transit": "pt"}


def _error_text(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error") or r.text)[:200]
    except ValueError:
        return r.text[:200]


class OneMapAuth:
    # After a rejected login, don't retry for this long: every routing call would
    # otherwise re-send the bad credentials (slow, and risks locking the account).
    FAILED_LOGIN_BACKOFF_S = 15 * 60

    def __init__(self, email: str, password: str, http: Optional[httpx.Client] = None):
        self.email, self.password = email.strip(), password.strip()
        self.http = http
        self._token: Optional[str] = None
        self._exp = 0.0
        self._failed_until = 0.0
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.email and self.password)

    @property
    def usable(self) -> bool:
        """Configured and not backing off after a rejected login."""
        return self.configured and time.time() >= self._failed_until

    def unavailable_reason(self) -> Optional[str]:
        if not self.configured:
            return "OneMap credentials not configured (ONEMAP_EMAIL / ONEMAP_PASSWORD)"
        if not self.usable:
            return f"OneMap login failed: {self.last_error}"
        return None

    def token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._exp - 3600:
                return self._token
            reason = self.unavailable_reason()
            if reason:
                raise ProviderError(reason)
            http = self.http or client()
            r = http.post(f"{BASE}/api/auth/post/getToken",
                          json={"email": self.email, "password": self.password})
            if r.status_code != 200:
                msg = _error_text(r)
                if "between 8 and 60" in msg:
                    # OneMap's message is misleading: its API rejects passwords shorter than 12
                    msg += " (OneMap's API actually needs a password of at least 12 characters)"
                self.last_error = f"HTTP {r.status_code}: {msg}"
                if 400 <= r.status_code < 500:
                    self._failed_until = time.time() + self.FAILED_LOGIN_BACKOFF_S
                raise ProviderError(f"OneMap login failed: {self.last_error}")
            self.last_error = None
            self._failed_until = 0.0
            data = r.json()
            self._token = data["access_token"]
            try:
                self._exp = float(data.get("expiry_timestamp") or 0)
            except (TypeError, ValueError):
                self._exp = 0
            if self._exp <= time.time():
                self._exp = time.time() + 3 * 24 * 3600
            return self._token


def _ms_to_offset(ms: Optional[float], depart_epoch: float) -> Optional[float]:
    if ms is None:
        return None
    return max(0.0, ms / 1000.0 - depart_epoch)


def parse_direct(data: dict, mode: Mode) -> Route:
    geom = data.get("route_geometry")
    if not geom:
        raise ProviderError(f"OneMap: {data.get('status_message') or data.get('error') or 'no route'}")
    coords = decode_polyline(geom, 5)
    summ = data.get("route_summary") or {}
    dur = float(summ.get("total_time") or 0)
    dist = float(summ.get("total_distance") or 0)
    leg = RouteLeg(mode={"drive": "DRIVE", "walk": "WALK", "cycle": "CYCLE"}[mode],
                   coords=coords, duration_s=dur, distance_m=dist)
    return Route(legs=[leg], duration_s=dur, distance_m=dist, mode=mode, provider="onemap")


def parse_pt(data: dict, depart: datetime) -> Route:
    plan = data.get("plan") or {}
    its = plan.get("itineraries") or []
    if not its:
        err = (data.get("error") or {}).get("msg") if isinstance(data.get("error"), dict) else data.get("error")
        raise ProviderError(f"OneMap pt: {err or 'no itinerary'}")
    it = min(its, key=lambda i: float(i.get("endTime") or 0) or float(i.get("duration") or 1e12))
    dep = depart.timestamp()
    legs: list[RouteLeg] = []
    for lg in it.get("legs", []):
        pts = (lg.get("legGeometry") or {}).get("points") or ""
        coords = decode_polyline(pts, 5) if pts else []
        f, t = lg.get("from") or {}, lg.get("to") or {}
        if not coords:
            coords = [(f.get("lat"), f.get("lon")), (t.get("lat"), t.get("lon"))]
        mode = str(lg.get("mode") or "WALK").upper()
        stops: list[TransitStop] = []
        if mode != "WALK":
            seq = [f, *(lg.get("intermediateStops") or []), t]
            for s in seq:
                if s.get("lat") is None:
                    continue
                when = s.get("arrival") or s.get("departure")
                stops.append(TransitStop(name=s.get("name") or "", lat=s["lat"], lng=s["lon"],
                                         t_s=_ms_to_offset(when, dep)))
        legs.append(RouteLeg(
            mode=mode, coords=coords, duration_s=float(lg.get("duration") or 0),
            distance_m=float(lg.get("distance") or 0),
            route_name=lg.get("route") or lg.get("routeShortName") or None,
            from_name=f.get("name"), to_name=t.get("name"),
            start_s=_ms_to_offset(lg.get("startTime"), dep), end_s=_ms_to_offset(lg.get("endTime"), dep),
            stops=stops))
    end = _ms_to_offset(it.get("endTime"), dep)
    dur = end if end is not None else float(it.get("duration") or sum(l.duration_s for l in legs))
    return Route(legs=legs, duration_s=dur, distance_m=sum(l.distance_m for l in legs),
                 mode="transit", provider="onemap")


class OneMapRouting:
    name = "onemap"

    def __init__(self, auth: OneMapAuth, per_minute: float = 200, http: Optional[httpx.Client] = None):
        self.auth = auth
        self.bucket = TokenBucket(per_minute)
        self.http = http

    def supports(self, mode: Mode) -> bool:
        return self.auth.usable and mode in ROUTE_TYPE

    def unavailable_reason(self) -> Optional[str]:
        return self.auth.unavailable_reason()

    def fetch(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> dict:
        params = {"start": f"{origin[0]:.6f},{origin[1]:.6f}", "end": f"{dest[0]:.6f},{dest[1]:.6f}",
                  "routeType": ROUTE_TYPE[mode]}
        if mode == "transit":
            params.update(date=depart.strftime("%m-%d-%Y"), time=depart.strftime("%H:%M:%S"),
                          mode="TRANSIT", maxWalkDistance="1000", numItineraries="3")
        self.bucket.take()
        http = self.http or client()
        r = http.get(f"{BASE}/api/public/routingsvc/route", params=params,
                     headers={"Authorization": self.auth.token()})
        if r.status_code != 200:
            raise ProviderError(f"OneMap route HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route:
        data = self.fetch(origin, dest, mode, depart)
        return parse_pt(data, depart) if mode == "transit" else parse_direct(data, mode)
