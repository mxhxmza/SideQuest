"""FastAPI app (DESIGN §7)."""
from __future__ import annotations

import logging
from datetime import date as Date
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.core import prayer
from app.deps import container
from app.models import GeocodeResult, ParseContext, ParseRequest, ParseResponse, TripPlan, TripRequest
from app.providers.base import ProviderError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Route-aware Stop Planner", version="0.1.0")

_c = container()
app.add_middleware(CORSMiddleware, allow_origins=_c.settings.cors_list, allow_origin_regex=r"https://.*\.vercel\.app",
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    c = container()
    modes = {m: [p.name for p in c.routing.providers if p.supports(m)] for m in ("drive", "walk", "cycle", "transit")}
    return {
        "status": "ok" if c.places is not None else "degraded",
        "region": c.region.key,
        "routing": modes,
        "routing_errors": c.routing.last_errors,
        "geocoding": [p.name for p in c.geocoder.active],
        "llm_default": c.parser.default,
        "onemap_configured": c.onemap_auth.configured,
        "onemap_error": c.onemap_auth.unavailable_reason() if c.onemap_auth.configured else None,
        "poi_db": c.places.info() if c.places else {"error": c.places_error},
        "cache": {"hits": c.cache.hits, "misses": c.cache.misses},
    }


@app.post("/api/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    c = container()
    ctx = ParseContext(departure_time=req.departure_time, timezone=c.region.timezone)
    return c.parser.parse(req.text, ctx, req.backend)


@app.post("/api/plan", response_model=TripPlan)
def plan(req: TripRequest):
    c = container()
    try:
        return c.planner().plan(req)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/prayer-times")
def prayer_times(lat: float, lng: float, date: Optional[Date] = None,
                 asr: Literal["shafii", "hanafi"] = "shafii", method: str = "SINGAPORE"):
    c = container()
    tz = c.region.timezone
    d = date or datetime.now(ZoneInfo(tz)).date()
    t = prayer.day_times(lat, lng, d, asr, method, tz)
    names = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
    return [{"name": n, "label": prayer.DISPLAY.get(n, n.title()), "time": t[n].isoformat()} for n in names]


@app.get("/api/geocode", response_model=list[GeocodeResult])
def geocode(q: str = Query(..., min_length=2), limit: int = Query(8, ge=1, le=20)):
    return container().geocoder.search(q, limit)


@app.get("/api/categories")
def categories():
    from app.core.tags import CATEGORIES
    return [{"key": k, "label": c.label, "icon": c.icon, "dwell_min": c.dwell_min, "kind": c.kind}
            for k, c in CATEGORIES.items()]
