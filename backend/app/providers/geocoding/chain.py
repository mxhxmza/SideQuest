"""Geocoder chain: first provider with results wins; local POI names as an offline fallback."""
from __future__ import annotations

import json
import logging
import re

import httpx

from app.cache import TTLCache
from app.models import GeocodeResult
from app.providers.base import ProviderError

log = logging.getLogger(__name__)


class LocalPoiGeocoding:
    name = "local"

    def __init__(self, places):
        self.places = places

    available = True

    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]:
        out = []
        for p in self.places.search_name(q, limit):
            t = p.tags
            addr = " ".join(x for x in [t.get("addr:housenumber"), t.get("addr:street"), t.get("addr:postcode")] if x)
            out.append(GeocodeResult(name=p.name or q, address=addr, lat=p.lat, lng=p.lng, source="local"))
        return out


RANKING_VERSION = 2


class ChainGeocoding:
    name = "chain"

    def __init__(self, providers: list, cache: TTLCache | None = None, ttl_s: float = 7 * 86400):
        self.providers = providers
        self.cache, self.ttl = cache, ttl_s

    @property
    def active(self) -> list:
        return [p for p in self.providers if getattr(p, "available", True)]

    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]:
        q = q.strip()
        if not q:
            return []
        active = self.active
        # provider set is part of the key: results cached while OneMap was down
        # must not keep shadowing OneMap once it works
        # "v": bump when ranking changes so cached lists are rebuilt
        k = TTLCache.key("geo", {"q": q.lower(), "l": limit, "p": [p.name for p in active], "v": RANKING_VERSION})
        if self.cache and (hit := self.cache.get(k)):
            return [GeocodeResult(**x) for x in json.loads(hit)]
        # Providers in order; stop at the first one with an exact name match.
        # Otherwise merge (earlier providers first) and re-rank by name match.
        results: list[GeocodeResult] = []
        for p in active:
            try:
                # ask for extra results so re-ranking can surface the exact match
                got = p.search(q, max(limit, 10))
            except (ProviderError, httpx.HTTPError, KeyError, ValueError) as e:
                log.warning("geocoder %s failed: %s", p.name, e)
                continue
            results += [r for r in got if not _near_dup(r, results)]
            if any(name_match_tier(q, r.name) == 3 for r in got):
                break
        results = rank_by_name(q, results)[:limit]
        if self.cache and results:
            self.cache.set(k, json.dumps([r.model_dump() for r in results]), self.ttl)
        return results


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def name_match_tier(q: str, name: str) -> int:
    """3 exact name, 2 name starts with query, 1 contains query, 0 otherwise."""
    nq, nn = _norm(q), _norm(name)
    if not nq:
        return 0
    if nn == nq:
        return 3
    if nn.startswith(nq):
        return 2
    if nq in nn:
        return 1
    return 0


def _near_dup(r: GeocodeResult, seen: list[GeocodeResult], radius_deg: float = 0.0015) -> bool:
    """Same name within ~150 m of a result we already have (from another provider)."""
    n = _norm(r.name)
    return any(_norm(s.name) == n and abs(s.lat - r.lat) < radius_deg and abs(s.lng - r.lng) < radius_deg
               for s in seen)


def rank_by_name(q: str, results: list[GeocodeResult]) -> list[GeocodeResult]:
    """Promote exact name matches; otherwise keep the providers' own order.

    Only *exact* matches move: a provider knows things a string match doesn't
    (OneMap ranks "Nanyang Technological University" first for "NTU", which a
    starts-with rule would bury under "NTU Innovation Centre" and "NTUC ...")."""
    return sorted(results, key=lambda r: name_match_tier(q, r.name) != 3)
