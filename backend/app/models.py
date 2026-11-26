"""Pydantic data model (DESIGN §4)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.core.tags import CATEGORY_KEYS, CUISINE_KEYS, DIETARY_KEYS

Mode = Literal["drive", "walk", "cycle", "transit"]
Category = Literal[CATEGORY_KEYS]  # type: ignore[valid-type]
Dietary = Literal[DIETARY_KEYS]  # type: ignore[valid-type]
Cuisine = Literal[CUISINE_KEYS]  # type: ignore[valid-type]
WindowType = Literal["minutes_in", "clock_time", "prayer", "any"]
PrayerName = Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
OpenState = Union[bool, Literal["unknown"]]


class Point(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None


class OsmFilter(BaseModel):
    """AND of key -> allowed values. ["*"] means any value."""
    tags: dict[str, list[str]]


class TimeWindow(BaseModel):
    type: WindowType = "any"
    # minutes_in: minutes (number); clock_time: "HH:MM"; prayer: PrayerName; any: None
    value: Optional[Union[float, str]] = None
    tolerance_min: Optional[float] = None
    relation: Literal["at", "before", "after"] = "at"
    # prayer windows: latest acceptable time "HH:MM" ("asr, anytime until 6pm");
    # replaces the default prayer start + 60 min end
    until: Optional[str] = None


class StopConstraints(BaseModel):
    open_at_eta: bool = True
    dietary: list[Dietary] = Field(default_factory=list)
    # food stops only: any of these cuisines ("Italian dinner"); empty = any cuisine
    cuisine: list[Cuisine] = Field(default_factory=list)


class StopRequest(BaseModel):
    id: str
    query: str = ""
    category: Category
    osm_filters: list[OsmFilter] = Field(default_factory=list)
    name_keywords: list[str] = Field(default_factory=list)
    time_window: TimeWindow = Field(default_factory=TimeWindow)
    constraints: StopConstraints = Field(default_factory=StopConstraints)
    dwell_min: Optional[float] = None
    label: Optional[str] = None
    icon: Optional[str] = None


class Prefs(BaseModel):
    asr_method: Literal["shafii", "hanafi"] = "shafii"
    prayer_method: str = "SINGAPORE"


class TripRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "drive"
    departure_time: datetime
    stops: list[StopRequest] = Field(default_factory=list)
    prefs: Prefs = Field(default_factory=Prefs)
    # stop_id -> osm_id chosen by the user ("Use this")
    pinned: dict[str, str] = Field(default_factory=dict)

    @field_validator("departure_time")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("departure_time must be timezone-aware (ISO 8601 with offset)")
        return v


class ParseRequest(BaseModel):
    text: str
    departure_time: Optional[datetime] = None
    backend: Optional[str] = None


class ParseResponse(BaseModel):
    backend_used: str
    stops: list[StopRequest]
    warnings: list[str] = Field(default_factory=list)
    unrecognized: list[str] = Field(default_factory=list)  # parts of the text that became no stop


# ---------------------------------------------------------------- routing --

class TransitStop(BaseModel):
    name: str = ""
    lat: float
    lng: float
    # seconds after departure when the vehicle halts here (if known)
    t_s: Optional[float] = None


class RouteLeg(BaseModel):
    mode: str  # DRIVE | WALK | CYCLE | BUS | SUBWAY | ...
    coords: list[tuple[float, float]]  # (lat, lng)
    duration_s: float
    distance_m: float = 0.0
    route_name: Optional[str] = None
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    # transit: start/end offsets from departure (includes waiting before boarding)
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    stops: list[TransitStop] = Field(default_factory=list)


class Route(BaseModel):
    legs: list[RouteLeg]
    duration_s: float
    distance_m: float
    mode: Mode
    provider: str


class GeocodeResult(BaseModel):
    name: str
    address: str = ""
    lat: float
    lng: float
    source: str = ""


class Place(BaseModel):
    id: int
    osm_id: str
    name: Optional[str] = None
    lat: float
    lng: float
    tags: dict[str, str] = Field(default_factory=dict)
    parent_id: Optional[int] = None
    is_container: bool = False


class ParseContext(BaseModel):
    departure_time: Optional[datetime] = None
    timezone: str = "Asia/Singapore"


# ------------------------------------------------------------------ plan --

class Evidence(BaseModel):
    text: str
    strength: Literal["strong", "weak"] = "strong"


class ParentRef(BaseModel):
    id: int
    osm_id: str
    name: Optional[str] = None


class PlaceCandidate(BaseModel):
    osm_id: str
    name: Optional[str] = None
    lat: float
    lng: float
    tags: dict[str, str] = Field(default_factory=dict)
    open_at_eta: OpenState = "unknown"
    detour_min: float
    detour_exact: bool = False
    eta: datetime
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    matched_stop_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    offset_m: float = 0.0
    along_s: float = 0.0
    parent: Optional[ParentRef] = None
    # "standalone" | "same_poi" | "container" | "covered"
    kind: str = "standalone"
    combined_note: Optional[str] = None
    hop_off: Optional[str] = None  # transit: stop/station to get off at
    # minutes spent at the place waiting for the window to open (arriving before a
    # prayer time starts); counted in the minutes added, on top of detour_min
    wait_min: float = 0.0


class EtaWindow(BaseModel):
    start: datetime
    end: datetime
    target: Optional[datetime] = None


class StopPlan(BaseModel):
    request: StopRequest
    eta_window: EtaWindow
    candidates: list[PlaceCandidate]
    chosen: Optional[PlaceCandidate] = None
    covered_by: Optional[str] = None  # stop id whose chosen place also serves this one
    added_min: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class PrayerOnRoute(BaseModel):
    name: str
    time: datetime
    position: Optional[Point] = None
    route_fraction: Optional[float] = None
    stop_id: Optional[str] = None
    note: Optional[str] = None


class RouteLegOut(BaseModel):
    mode: str
    route_name: Optional[str] = None
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    duration_s: float
    distance_m: float
    geometry: list[tuple[float, float]]  # (lng, lat) GeoJSON order


class RouteOut(BaseModel):
    geometry: list[tuple[float, float]]  # (lng, lat) GeoJSON order
    duration_s: float
    distance_m: float
    mode: Mode
    provider: str
    legs: list[RouteLegOut] = Field(default_factory=list)


class TimelineRow(BaseModel):
    kind: Literal["depart", "stop", "prayer", "arrive"]
    time: datetime
    label: str
    stop_id: Optional[str] = None
    prayer: Optional[str] = None


class LegLink(BaseModel):
    label: str
    url: str


class TripPlan(BaseModel):
    route: RouteOut
    departure_time: datetime
    stops: list[StopPlan]
    prayer_times: list[PrayerOnRoute]
    timeline: list[TimelineRow]
    total_added_min: float
    arrival_eta: datetime
    gmaps_url: str
    gmaps_leg_urls: list[LegLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
