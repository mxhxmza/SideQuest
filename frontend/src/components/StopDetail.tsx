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
      <p className="mb-2 text-[11px] text-slate-500">
        {fmtWindow(req.time_window)} · window {fmtTime(stop.eta_window.start)}–{fmtTime(stop.eta_window.end)} · stay {req.dwell_min} min
      </p>
      {stop.candidates.length === 0 && <p className="text-sm text-slate-500">No options found.</p>}
      <ol className="space-y-2">
        {stop.candidates.map((c, i) => {
          const chosen = stop.chosen?.osm_id === c.osm_id;
          const weak = c.evidence.some((e) => e.strength === "weak");
          return (
            <li
              key={c.osm_id + i}
              className={`animate-fade-up rounded-2xl border p-3 text-sm transition ${
                chosen ? "border-brand-300 bg-brand-50/70 shadow-sm" : "border-slate-200 bg-white hover:border-brand-200 hover:shadow-md"
              }`}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-bold text-slate-900">
                    <span className="mr-1 text-slate-400">{i + 1}.</span>
                    {c.name ?? "Unnamed place"}
                  </div>
                  {c.parent?.name && <div className="text-xs text-slate-500">in {c.parent.name}</div>}
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <span className="badge bg-brand-100 text-brand-800">
                      {fmtAdded(addedMin(c))}
                      {!c.detour_exact && " est."}
                    </span>
                    <span className="badge bg-slate-100 text-slate-700">ETA {fmtTime(c.eta)}</span>
                    {(c.wait_min ?? 0) >= 1 && (
                      <span className="badge bg-amber-100 text-amber-800">⏳ waits {Math.round(c.wait_min!)} min</span>
                    )}
                    <OpenBadge state={c.open_at_eta} />
                    <span className="badge bg-slate-100 text-slate-500">{fmtDistance(c.offset_m)} off route</span>
                    {c.hop_off && <span className="badge bg-sky-100 text-sky-700">🚏 {c.hop_off}</span>}
                  </div>
                  {c.combined_note && <p className="mt-1.5 text-xs font-medium text-violet-700">★ {c.combined_note}</p>}
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {c.evidence.map((e) => (
                      <span
                        key={e.text}
                        className={`badge font-medium ${
                          e.strength === "strong"
                            ? "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200"
                            : "bg-amber-50 text-amber-800 ring-1 ring-amber-200"
                        }`}
                        title={e.strength === "strong" ? "Tagged in OpenStreetMap" : "Weak evidence — a hint, not a verified fact"}
                      >
                        {e.strength === "strong" ? "✓" : "?"} {e.text.replace(/^OSM /, "")}
                      </span>
                    ))}
                  </div>
                  {weak && diet.includes("halal") && (
                    <p className="mt-1.5 text-[11px] text-amber-700">Not verified halal — check MUIS certification on site.</p>
                  )}
                </div>
                <div className="shrink-0">
                  {chosen ? (
                    <span className="badge bg-brand-600 px-2.5 py-1 text-white">✓ chosen</span>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      className="rounded-xl bg-slate-900 px-3 py-1.5 text-xs font-bold text-white shadow transition hover:-translate-y-0.5 hover:bg-brand-700 disabled:opacity-50"
                      onClick={() => onUse(c.osm_id)}
                    >
                      Use this
                    </button>
                  )}
                </div>
              </div>
              <button
                type="button"
                className="mt-2 text-[11px] font-semibold text-slate-500 hover:text-brand-700"
                onClick={() => setOpen(open === c.osm_id ? null : c.osm_id)}
              >
                {open === c.osm_id ? "Hide" : "Why this rank?"} · score {c.score.toFixed(1)}
              </button>
              {open === c.osm_id && (
                <table className="mt-1 w-full animate-slide-down text-xs">
                  <tbody>
                    {Object.entries(c.score_breakdown).map(([k, v]) => (
                      <tr key={k} className="border-t border-slate-100">
                        <td className="py-1 text-slate-600">{BREAKDOWN_LABELS[k] ?? k}</td>
                        <td className={`py-1 text-right font-mono ${v < 0 ? "text-emerald-700" : ""}`}>
                          {v > 0 ? "+" : ""}
                          {v.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-slate-300 font-bold">
                      <td className="py-1">Score (minutes, lower is better)</td>
                      <td className="py-1 text-right font-mono">{c.score.toFixed(1)}</td>
                    </tr>
                  </tbody>
                </table>
              )}
              {c.tags.opening_hours && <p className="mt-1 text-[11px] text-slate-400">Hours: {c.tags.opening_hours}</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
