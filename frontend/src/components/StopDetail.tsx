import { useState } from "react";
import type { StopPlan } from "../types";
import { BREAKDOWN_LABELS, addedMin, fmtAdded, fmtDistance, fmtTime, fmtWindow } from "../lib/format";
import { OpenBadge } from "./Timeline";

interface Props {
  stop: StopPlan;
  busy: boolean;
  onUse: (osmId: string) => void;
}

/** Ranked options for one stop, shown inline under its timeline row. */
export default function StopDetail({ stop, busy, onUse }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const req = stop.request;
  const diet = req.constraints.dietary;
  return (
    <section aria-label={`Options for ${req.label}`}>
      <p className="mb-2 text-[11px] text-slate-400">
        {fmtWindow(req.time_window)} · window {fmtTime(stop.eta_window.start)}–{fmtTime(stop.eta_window.end)} · stay {req.dwell_min} min
      </p>
      {stop.candidates.length === 0 && <p className="text-sm text-slate-400">No options found.</p>}
      <ol className="space-y-2">
        {stop.candidates.map((c, i) => {
          const chosen = stop.chosen?.osm_id === c.osm_id;
          const weak = c.evidence.some((e) => e.strength === "weak");
          return (
            <li
              key={c.osm_id + i}
              className={`animate-fade-up rounded-2xl border p-3 text-sm transition ${
                chosen ? "border-amber-300/40 bg-amber-300/[0.07]" : "border-white/10 bg-white/[0.03] hover:border-brand-400/40 hover:bg-white/[0.06]"
              }`}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-bold text-white">
                    <span className="mr-1 font-display text-slate-500">{i + 1}.</span>
                    {c.name ?? "Unnamed place"}
                  </div>
                  {c.parent?.name && <div className="text-xs text-slate-400">in {c.parent.name}</div>}
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <span className="badge bg-brand-400/15 text-brand-200">
                      {fmtAdded(addedMin(c))}
                      {!c.detour_exact && " est."}
                    </span>
                    <span className="badge bg-white/5 text-slate-300">ETA {fmtTime(c.eta)}</span>
                    {(c.wait_min ?? 0) >= 1 && (
                      <span className="badge bg-amber-400/15 text-amber-200">⏳ waits {Math.round(c.wait_min!)} min</span>
                    )}
                    <OpenBadge state={c.open_at_eta} />
                    <span className="badge bg-white/5 text-slate-400">{fmtDistance(c.offset_m)} off route</span>
                    {c.hop_off && <span className="badge bg-sky-400/15 text-sky-200">🚏 {c.hop_off}</span>}
                  </div>
                  {c.combined_note && <p className="mt-1.5 text-xs font-medium text-violet-300">⚡ {c.combined_note}</p>}
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {c.evidence.map((e) => (
                      <span
                        key={e.text}
                        className={`badge font-medium ${
                          e.strength === "strong"
                            ? "bg-emerald-400/10 text-emerald-200 ring-1 ring-emerald-400/25"
                            : "bg-amber-400/10 text-amber-200 ring-1 ring-amber-400/25"
                        }`}
                        title={e.strength === "strong" ? "Tagged in OpenStreetMap" : "Weak evidence — a hint, not a verified fact"}
                      >
                        {e.strength === "strong" ? "✓" : "?"} {e.text.replace(/^OSM /, "")}
                      </span>
                    ))}
                  </div>
                  {weak && diet.includes("halal") && (
                    <p className="mt-1.5 text-[11px] text-amber-300">Not verified halal — check MUIS certification on site.</p>
                  )}
                </div>
                <div className="shrink-0">
                  {chosen ? (
                    <span className="badge bg-gradient-to-b from-amber-200 to-amber-400 px-2.5 py-1 font-display tracking-wide text-ink-950">★ chosen</span>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      className="btn-3d px-3 py-1.5 text-[11px]"
                      onClick={() => onUse(c.osm_id)}
                    >
                      Use this
                    </button>
                  )}
                </div>
              </div>
              <button
                type="button"
                className="mt-2 text-[11px] font-semibold text-slate-400 hover:text-brand-300"
                onClick={() => setOpen(open === c.osm_id ? null : c.osm_id)}
              >
                {open === c.osm_id ? "Hide" : "Why this rank?"} · score {c.score.toFixed(1)}
              </button>
              {open === c.osm_id && (
                <table className="mt-1 w-full animate-slide-down text-xs">
                  <tbody>
                    {Object.entries(c.score_breakdown).map(([k, v]) => (
                      <tr key={k} className="border-t border-white/5">
                        <td className="py-1 text-slate-400">{BREAKDOWN_LABELS[k] ?? k}</td>
                        <td className={`py-1 text-right font-mono ${v < 0 ? "text-emerald-300" : "text-slate-200"}`}>
                          {v > 0 ? "+" : ""}
                          {v.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-white/20 font-bold text-white">
                      <td className="py-1">Score (minutes, lower is better)</td>
                      <td className="py-1 text-right font-mono">{c.score.toFixed(1)}</td>
                    </tr>
                  </tbody>
                </table>
              )}
              {c.tags.opening_hours && <p className="mt-1 text-[11px] text-slate-500">Hours: {c.tags.opening_hours}</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
