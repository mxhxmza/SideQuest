// Mirrors backend/app/models.py

export type Mode = "drive" | "walk" | "cycle" | "transit";
export type WindowType = "minutes_in" | "clock_time" | "prayer" | "any";
export type OpenState = boolean | "unknown";

export interface Point {
  lat: number;
  lng: number;
  name?: string | null;
}

export interface TimeWindow {
  type: WindowType;
  value?: number | string | null;
  tolerance_min?: number | null;
  relation?: "at" | "before" | "after";
  /** prayer windows: latest time "HH:MM" ("asr, anytime until 6pm") */
  until?: string | null;
}

export interface StopRequest {
  id: string;
  query: string;
  category: string;
  osm_filters?: { tags: Record<string, string[]> }[];
  name_keywords?: string[];
  time_window: TimeWindow;
  /** cuisine: food stops only, any of these ("italian"); empty = any */
  constraints: { open_at_eta: boolean; dietary: string[]; cuisine?: string[] };
  dwell_min?: number | null;
  label?: string | null;
  icon?: string | null;
}

export interface Evidence {
  text: string;
  strength: "strong" | "weak";
}

export interface PlaceCandidate {
  osm_id: string;
  name?: string | null;
  lat: number;
  lng: number;
  tags: Record<string, string>;
  open_at_eta: OpenState;
  detour_min: number;
  detour_exact: boolean;
  eta: string;
  score: number;
  score_breakdown: Record<string, number>;
  matched_stop_ids: string[];
  evidence: Evidence[];
  offset_m: number;
  along_s: number;
  parent?: { id: number; osm_id: string; name?: string | null } | null;
  kind: "standalone" | "same_poi" | "container" | "covered";
  combined_note?: string | null;
  hop_off?: string | null;
  /** minutes waiting there for the prayer time to start; part of the minutes added */
  wait_min?: number;
}

export interface StopPlan {
  request: StopRequest;
  eta_window: { start: string; end: string; target?: string | null };
  candidates: PlaceCandidate[];
  chosen?: PlaceCandidate | null;
  covered_by?: string | null;
  added_min: number;
  warnings: string[];
}

export interface PrayerOnRoute {
  name: string;
  time: string;
  position?: Point | null;
  route_fraction?: number | null;
  stop_id?: string | null;
  note?: string | null;
}

export interface TimelineRow {
  kind: "depart" | "stop" | "prayer" | "arrive";
  time: string;
  label: string;
  stop_id?: string | null;
  prayer?: string | null;
}

export interface RouteLegOut {
  mode: string;
  route_name?: string | null;
  from_name?: string | null;
  to_name?: string | null;
  duration_s: number;
  distance_m: number;
  geometry: [number, number][];
}

export interface TripPlan {
  route: {
    geometry: [number, number][];
    duration_s: number;
    distance_m: number;
    mode: Mode;
    provider: string;
    legs: RouteLegOut[];
  };
  departure_time: string;
  stops: StopPlan[];
  prayer_times: PrayerOnRoute[];
  timeline: TimelineRow[];
  total_added_min: number;
  arrival_eta: string;
  gmaps_url: string;
  gmaps_leg_urls: { label: string; url: string }[];
  warnings: string[];
}

export interface TripRequest {
  origin: Point;
  destination: Point;
  mode: Mode;
  departure_time: string;
  stops: StopRequest[];
  prefs?: { asr_method?: "shafii" | "hanafi"; prayer_method?: string };
  pinned: Record<string, string>;
}

export interface ParseResponse {
  backend_used: string;
  stops: StopRequest[];
  warnings: string[];
  unrecognized: string[];
}

export interface GeocodeResult {
  name: string;
  address: string;
  lat: number;
  lng: number;
  source: string;
}

/** The suggestion list open under the Start or Finish box, previewed on the map. */
export interface PlacePreview {
  kind: "origin" | "dest";
  results: GeocodeResult[];
  /** the highlighted suggestion (arrow keys / mouse) */
  active: number;
}

export interface Category {
  key: string;
  label: string;
  icon: string;
  dwell_min: number;
  kind: string;
}

export interface Cuisine {
  key: string;
  label: string;
}

export interface Health {
  status: string;
  region: string;
  routing: Record<Mode, string[]>;
  geocoding: string[];
  llm_default: string;
  onemap_configured: boolean;
  onemap_error?: string | null;
  poi_db: Record<string, string>;
}
