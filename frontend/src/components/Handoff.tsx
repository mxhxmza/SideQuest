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
      ? legUrls([{ label: origin.name ?? "Start", at: origin }, ...included, { label: destination.name ?? "Destination", at: destination }], mode)
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
      <h3 className="mb-1 flex items-center gap-2 font-display text-[15px] font-semibold tracking-wide text-white">
        <span className="hex flex h-7 w-8 items-center justify-center bg-gradient-to-br from-sky-300 to-blue-600 text-sm">🚀</span>
        Launch in Google Maps
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
                aria-pressed={on}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                  on ? "bg-sky-400/20 text-sky-100 ring-1 ring-sky-300/40" : "bg-white/5 text-slate-500 line-through ring-1 ring-white/5"
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
          <p className="mb-2 text-xs text-slate-400">Google Maps can't add stops to public-transport directions, so here's one link per leg:</p>
          <ul className="space-y-1.5">
            {legs.map((l, i) => (
              <li key={l.url}>
                <a
                  className="flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-sm font-medium text-slate-200 ring-1 ring-white/10 transition hover:bg-sky-400/15 hover:text-white"
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className="hex flex h-5 w-6 items-center justify-center bg-sky-400/80 font-display text-[10px] font-bold text-ink-950">{i + 1}</span>
                  {l.label} <span className="ml-auto">↗</span>
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          {included.length > MAX_WAYPOINTS && <p className="mb-2 text-xs text-amber-300">Google Maps takes at most {MAX_WAYPOINTS} stops; extras are dropped.</p>}
          <a className="btn-3d btn-blue mt-1 w-full" href={url} target="_blank" rel="noopener noreferrer">
            ▶ Open in Google Maps
          </a>
          <p className="mt-3 text-center text-[11px] text-slate-500">Tap a stop above to leave it out. Mobile may show fewer stops.</p>
        </>
      )}
    </section>
  );
}
