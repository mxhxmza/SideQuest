"""OneMap Search (needs a token since 2024; shares OneMapAuth with routing)."""
from __future__ import annotations

from app.models import GeocodeResult
from app.providers.base import ProviderError
from app.providers.http import client
from app.providers.routing.onemap import BASE, OneMapAuth


def _title(s: str) -> str:
    return s.title() if s.isupper() else s


class OneMapGeocoding:
    name = "onemap"

    def __init__(self, auth: OneMapAuth):
        self.auth = auth

    @property
    def available(self) -> bool:
        return self.auth.usable

    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]:
        r = client().get(f"{BASE}/api/common/elastic/search",
                         params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
                         headers={"Authorization": self.auth.token()})
        if r.status_code != 200:
            raise ProviderError(f"OneMap search HTTP {r.status_code}")
        out = []
        for it in (r.json().get("results") or [])[:limit]:
            name = it.get("BUILDING") if it.get("BUILDING") not in (None, "", "NIL") else it.get("SEARCHVAL")
            out.append(GeocodeResult(name=_title(name or q), address=_title(it.get("ADDRESS") or ""),
                                     lat=float(it["LATITUDE"]), lng=float(it["LONGITUDE"]), source="onemap"))
        return out
