"""Keyless Photon (komoot) geocoder restricted to the region bbox — fallback (D11)."""
from __future__ import annotations

from app.models import GeocodeResult
from app.providers.base import ProviderError
from app.providers.http import client


class PhotonGeocoding:
    name = "photon"

    def __init__(self, url: str, bbox: tuple[float, float, float, float], center: tuple[float, float]):
        self.url = url
        self.bbox = bbox
        self.center = center

    @property
    def available(self) -> bool:
        return bool(self.url)

    def search(self, q: str, limit: int = 8) -> list[GeocodeResult]:
        a, b, c, d = self.bbox
        r = client().get(self.url, params={"q": q, "limit": limit, "lang": "en",
                                           "bbox": f"{b},{a},{d},{c}",
                                           "lat": self.center[0], "lon": self.center[1]})
        if r.status_code != 200:
            raise ProviderError(f"Photon HTTP {r.status_code}")
        out = []
        for f in r.json().get("features", []):
            p = f.get("properties", {})
            lng, lat = f["geometry"]["coordinates"]
            if not (a <= lat <= c and b <= lng <= d) or p.get("country") not in (None, "Singapore"):
                continue
            street = " ".join(x for x in [p.get("housenumber"), p.get("street")] if x)
            addr = ", ".join(x for x in [street, p.get("district") or p.get("locality"), p.get("postcode")] if x)
            out.append(GeocodeResult(name=p.get("name") or street or q, address=addr, lat=lat, lng=lng,
                                     source="photon"))
        return out
