"""Fallback chain + cache wrapper for routing providers."""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.cache import TTLCache
from app.models import Mode, Route
from app.providers.base import LatLng, ProviderError, RoutingProvider

log = logging.getLogger(__name__)


class FallbackRouting:
    name = "chain"

    def __init__(self, providers: list[RoutingProvider]):
        self.providers = providers
        self.last_errors: dict[str, str] = {}

    def supports(self, mode: Mode) -> bool:
        return any(p.supports(mode) for p in self.providers)

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route:
        errors: list[str] = []
        for p in self.providers:
            if not p.supports(mode):
                continue
            try:
                return p.route(origin, dest, mode, depart)
            except (ProviderError, httpx.HTTPError, KeyError, ValueError) as e:
                msg = f"{p.name}: {e}"
                log.warning("routing provider failed: %s", msg)
                self.last_errors[p.name] = str(e)
                errors.append(msg)
        if not errors:
            reasons = [r for p in self.providers if (r := getattr(p, "unavailable_reason", lambda: None)())]
            hint = " " + "; ".join(reasons) if reasons else ""
            if mode == "transit" and not reasons:
                hint = " Public transport routing needs OneMap credentials (ONEMAP_EMAIL / ONEMAP_PASSWORD)."
            raise ProviderError(f"No routing provider available for '{mode}'.{hint}")
        raise ProviderError("All routing providers failed: " + "; ".join(errors))

    def duration_s(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> float:
        """Duration only (cheaper: providers that can skip geometry do so)."""
        errors: list[str] = []
        for p in self.providers:
            if not p.supports(mode):
                continue
            try:
                fn = getattr(p, "duration_s", None)
                return fn(origin, dest, mode, depart) if fn else p.route(origin, dest, mode, depart).duration_s
            except (ProviderError, httpx.HTTPError, KeyError, ValueError) as e:
                self.last_errors[p.name] = str(e)
                errors.append(f"{p.name}: {e}")
        raise ProviderError("All routing providers failed: " + "; ".join(errors) if errors
                            else f"No routing provider supports mode '{mode}'")


    def matrix_s(self, points: list[LatLng], mode: Mode) -> list[list[float]]:
        for p in self.providers:
            fn = getattr(p, "matrix_s", None)
            if fn is None or not p.supports(mode):
                continue
            try:
                return fn(points, mode)
            except NotImplementedError:
                continue  # e.g. FOSSGIS: try the next OSRM instance
            except (ProviderError, httpx.HTTPError, KeyError, ValueError) as e:
                self.last_errors[p.name] = str(e)
                break
        raise NotImplementedError("no matrix-capable provider for this mode")

    def primary_for(self, mode: Mode) -> str | None:
        return next((p.name for p in self.providers if p.supports(mode)), None)

    def has_matrix(self, mode: Mode) -> bool:
        return any(p.supports(mode) and getattr(p, "matrix", False) for p in self.providers)


class CachedRouting:
    def __init__(self, inner: RoutingProvider, cache: TTLCache, ttl_s: float):
        self.inner, self.cache, self.ttl = inner, cache, ttl_s
        self.name = inner.name

    def supports(self, mode: Mode) -> bool:
        return self.inner.supports(mode)

    def has_matrix(self, mode: Mode) -> bool:
        fn = getattr(self.inner, "has_matrix", None)
        return bool(fn and fn(mode))

    def _provider_tag(self, mode: Mode) -> str | None:
        """Which provider would answer now — part of the cache key, so a route cached
        while OneMap was unavailable doesn't shadow OneMap once it works."""
        fn = getattr(self.inner, "primary_for", None)
        return fn(mode) if fn else self.inner.name

    def matrix_s(self, points: list[LatLng], mode: Mode) -> list[list[float]]:
        inner = getattr(self.inner, "matrix_s", None)
        if inner is None or not self.has_matrix(mode):
            raise NotImplementedError
        k = TTLCache.key("mx", {"p": [[round(a, 5), round(b, 5)] for a, b in points], "m": mode})
        hit = self.cache.get(k)
        if hit:
            import json
            return json.loads(hit)
        m = inner(points, mode)
        import json
        self.cache.set(k, json.dumps(m), self.ttl)
        return m

    def duration_s(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> float:
        payload = {"o": [round(origin[0], 5), round(origin[1], 5)],
                   "d": [round(dest[0], 5), round(dest[1], 5)], "m": mode, "p": self._provider_tag(mode)}
        if mode == "transit":
            payload["t"] = int(depart.timestamp() // 600 * 600)
        k = TTLCache.key("dur", payload)
        hit = self.cache.get(k)
        if hit:
            return float(hit)
        fn = getattr(self.inner, "duration_s", None)
        v = fn(origin, dest, mode, depart) if fn else self.inner.route(origin, dest, mode, depart).duration_s
        self.cache.set(k, repr(float(v)), self.ttl)
        return float(v)

    def route(self, origin: LatLng, dest: LatLng, mode: Mode, depart: datetime) -> Route:
        payload = {"o": [round(origin[0], 5), round(origin[1], 5)],
                   "d": [round(dest[0], 5), round(dest[1], 5)], "m": mode, "p": self._provider_tag(mode)}
        if mode == "transit":
            # timetable matters; bucket to 10 minutes
            ts = int(depart.timestamp() // 600 * 600)
            payload["t"] = ts
        k = TTLCache.key("route", payload)
        hit = self.cache.get(k)
        if hit:
            r = Route.model_validate_json(hit)
            if mode == "transit":
                # offsets are relative to the cached departure bucket; shift to this one
                delta = depart.timestamp() - payload["t"]
                if abs(delta) > 1:
                    for leg in r.legs:
                        if leg.start_s is not None:
                            leg.start_s = max(0.0, leg.start_s - delta)
                        if leg.end_s is not None:
                            leg.end_s = max(0.0, leg.end_s - delta)
                        for s in leg.stops:
                            if s.t_s is not None:
                                s.t_s = max(0.0, s.t_s - delta)
                    r.duration_s = max(0.0, r.duration_s - delta)
            return r
        r = self.inner.route(origin, dest, mode, depart)
        if mode == "transit":
            # normalise offsets to the bucket start so the shift above is consistent
            delta = depart.timestamp() - payload["t"]
            stored = r.model_copy(deep=True)
            for leg in stored.legs:
                if leg.start_s is not None:
                    leg.start_s += delta
                if leg.end_s is not None:
                    leg.end_s += delta
                for s in leg.stops:
                    if s.t_s is not None:
                        s.t_s += delta
            stored.duration_s += delta
            self.cache.set(k, stored.model_dump_json(), self.ttl)
        else:
            self.cache.set(k, r.model_dump_json(), self.ttl)
        return r
