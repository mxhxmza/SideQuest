import { useMemo, useState } from "react";
import type { Point, TripPlan } from "../types";
import { gmapsUrl, legUrls, MAX_WAYPOINTS } from "../lib/deeplink";

interface Props {
  plan: TripPlan;
  origin: Point;
  destination: Point;
}

export default function Handoff({ plan, origin, destination }: Props) {
  // distinct chosen places in route order
  const places = useMemo(() => {
    const seen = new Set<string>();
    return plan.stops
      .filter((s) => s.chosen && !s.covered_by)
      .sort((a, b) => a.chosen!.along_s - b.chosen!.along_s)
      .filter((s) => (seen.has(s.chosen!.osm_id) ? false : (seen.add(s.chosen!.osm_id), true)))
      .map((s) => ({ id: s.request.id, label: s.chosen!.name ?? s.request.label ?? "Stop", at: s.chosen!, icon: s.request.icon }));
  }, [plan]);
  const [skip, setSkip] = useState<Set<string>>(new Set());
  const included = places.filter((p) => !skip.has(p.id));
  const mode = plan.route.mode;
  const url = gmapsUrl(origin, destination, included.map((p) => p.at), mode);
  const legs =
    mode === "transit"
      ? legUrls(
          [{ label: origin.name ?? "Start", at: origin }, ...included, { label: destination.name ?? "Destination", at: destination }],
          mode,
        )
      : [];
  const toggle = (id: string) =>
    setSkip((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  return (
    <section className="card animate-fade-up p-4">
      <h3 className="mb-1 flex items-center gap-2 font-bold text-slate-900">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 via-emerald-500 to-amber-400 text-sm text-white">
          ➜
        </span>
        Take it to Google Maps
      </h3>
      {places.length > 0 && (
        <div className="my-3 flex flex-wrap gap-1.5">
          {places.map((p) => {
            const on = !skip.has(p.id);
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => toggle(p.id)}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                  on ? "bg-brand-600 text-white shadow" : "bg-slate-100 text-slate-400 line-through"
                }`}
              >
                {p.icon} {p.label}
              </button>
            );
          })}
        </div>
      )}
      {mode === "transit" ? (
        <>
          <p className="mb-2 text-xs text-slate-500">Google Maps can't add stops to public-transport directions, so here's one link per leg:</p>
          <ul className="space-y-1.5">
            {legs.map((l, i) => (
              <li key={l.url}>
                <a
                  className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-brand-50 hover:text-brand-800"
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold shadow">{i + 1}</span>
                  {l.label} <span className="ml-auto">↗</span>
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          {included.length > MAX_WAYPOINTS && (
            <p className="mb-2 text-xs text-amber-700">Google Maps takes at most {MAX_WAYPOINTS} stops; extras are dropped.</p>
          )}
          <a className="btn-primary w-full" href={url} target="_blank" rel="noopener noreferrer">
            Open in Google Maps ↗
          </a>
          <p className="mt-2 text-center text-[11px] text-slate-400">Tap a stop above to leave it out. Mobile may show fewer stops.</p>
        </>
      )}
    </section>
  );
}
