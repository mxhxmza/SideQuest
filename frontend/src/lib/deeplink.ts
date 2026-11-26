import type { Mode } from "../types";

// Keyless Google Maps directions links (mirrors backend/app/core/deeplink.py).
export const TRAVELMODE: Record<Mode, string> = {
  drive: "driving",
  walk: "walking",
  cycle: "bicycling",
  transit: "transit",
};
export const MAX_WAYPOINTS = 9;

type LL = { lat: number; lng: number };
const fmt = (p: LL) => `${p.lat.toFixed(6)},${p.lng.toFixed(6)}`;

export function gmapsUrl(origin: LL, destination: LL, waypoints: LL[], mode: Mode): string {
  const parts = [
    "api=1",
    `origin=${fmt(origin)}`,
    `destination=${fmt(destination)}`,
    `travelmode=${TRAVELMODE[mode]}`,
  ];
  // Google ignores waypoints for transit — callers offer one link per leg instead.
  if (waypoints.length && mode !== "transit") {
    parts.push(`waypoints=${waypoints.slice(0, MAX_WAYPOINTS).map(fmt).join("|")}`);
  }
  return `https://www.google.com/maps/dir/?${parts.join("&")}`;
}

export function legUrls(points: { label: string; at: LL }[], mode: Mode): { label: string; url: string }[] {
  const out: { label: string; url: string }[] = [];
  for (let i = 0; i + 1 < points.length; i++) {
    out.push({
      label: `${points[i].label} → ${points[i + 1].label}`,
      url: gmapsUrl(points[i].at, points[i + 1].at, [], mode),
    });
  }
  return out;
}
