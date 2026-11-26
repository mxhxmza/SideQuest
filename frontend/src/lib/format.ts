export const TZ = "Asia/Singapore";

const timeFmt = new Intl.DateTimeFormat("en-SG", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ });
const dayFmt = new Intl.DateTimeFormat("en-SG", { weekday: "short", day: "numeric", month: "short", timeZone: TZ });

/** "13:05" in Singapore time. */
export function fmtTime(iso: string | Date): string {
  return timeFmt.format(typeof iso === "string" ? new Date(iso) : iso);
}

export function fmtDay(iso: string | Date): string {
  return dayFmt.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** "+6 min", "+0 min", "+1 h 05 min" */
export function fmtAdded(min: number): string {
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `+${m} min`;
  return `+${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

/** Minutes a candidate adds to the trip: detour + any wait for a prayer time to start. */
export function addedMin(c: { detour_min: number; wait_min?: number }): number {
  return c.detour_min + (c.wait_min ?? 0);
}

/** 2520 s → "42 min", 5400 → "1 h 30 min" */
export function fmtDuration(seconds: number): string {
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${r} min` : `${h} h`;
}

export function fmtDistance(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(m < 10_000 ? 1 : 0)} km`;
}

/** Value for <input type="datetime-local"> in Singapore time, rounded up to 5 min. */
export function localInputNow(now = new Date()): string {
  const ms = Math.ceil(now.getTime() / 300_000) * 300_000;
  const sg = new Date(ms + 8 * 3600_000); // SG is UTC+8, no DST
  return sg.toISOString().slice(0, 16);
}

/** "2026-11-27T12:30" (SG wall clock) → "2026-11-27T12:30:00+08:00" */
export function inputToIso(local: string): string {
  return `${local.length === 16 ? local + ":00" : local}+08:00`;
}

export const BREAKDOWN_LABELS: Record<string, string> = {
  detour: "Detour",
  closed_at_eta: "Closed at ETA",
  hours_unknown: "Hours unknown",
  outside_window: "Outside time window",
  no_name: "No name",
  weak_dietary_evidence: "Weak dietary evidence",
  name_hint_only: "Matched by name only",
  combine_bonus: "Combined-stop bonus",
  off_target: "Distance from target time",
  pushes_other_stops: "Pushes later stops past their window",
  wait: "Waiting for prayer time",
};

export function fmtWindow(w: {
  type: string;
  value?: number | string | null;
  relation?: string;
  until?: string | null;
}): string {
  const rel = w.relation === "before" ? "before " : w.relation === "after" ? "after " : "";
  switch (w.type) {
    case "clock_time":
      return `${rel || "~"}${w.value}`;
    case "minutes_in":
      return `${rel}${w.value} min in`;
    case "prayer":
      return `${rel || "@"}${PRAYER_LABEL[String(w.value)] ?? w.value}${w.until ? `–${w.until}` : ""}`;
    default:
      return "any time";
  }
}

export const PRAYER_LABEL: Record<string, string> = {
  fajr: "Subuh",
  dhuhr: "Zohor",
  asr: "Asar",
  maghrib: "Maghrib",
  isha: "Isyak",
};
