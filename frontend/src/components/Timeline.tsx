import type { ReactNode } from "react";
import type { PlaceCandidate, TripPlan } from "../types";
import { addedMin, fmtAdded, fmtTime, PRAYER_LABEL } from "../lib/format";
import { WORSHIP } from "../lib/game";

interface Props {
  plan: TripPlan;
  selectedStopId: string | null;
  onSelectStop: (id: string | null) => void;
  onSuggestMosque: (prayer: string) => void;
  renderDetail: (stopId: string) => ReactNode;
  /** show Islamic prayer times along the route (rows + "add a mosque") */
  showPrayers: boolean;
  /** offered when the route has prayer times: switch them on/off */
  onTogglePrayers?: () => void;
}

export function OpenBadge({ state }: { state: PlaceCandidate["open_at_eta"] }) {
  if (state === true) return <span className="badge bg-emerald-400/15 text-emerald-300">● open</span>;
  if (state === false) return <span className="badge bg-rose-400/15 text-rose-300">● closed</span>;
  return <span className="badge bg-white/5 text-slate-400">hours unknown</span>;
}

const KIND_STYLE: Record<string, string> = {
  meal: "from-orange-300 to-rose-500",
  worship: "from-amber-200 to-orange-500",
  search: "from-violet-300 to-fuchsia-500",
  default: "from-brand-300 to-cyan-500",
};

function gradFor(category: string): string {
  if (category === "keyword") return KIND_STYLE.search;
  if (["meal", "hawker", "cafe", "ice_cream", "bakery"].includes(category)) return KIND_STYLE.meal;
  if (WORSHIP.has(category)) return KIND_STYLE.worship;
  return KIND_STYLE.default;
}

/** The trip as a level path: start, checkpoints (stops), prayer times, finish. */
export default function Timeline({ plan, selectedStopId, onSelectStop, onSuggestMosque, renderDetail, showPrayers, onTogglePrayers }: Props) {
  const stopIndex = new Map(plan.stops.map((s, i) => [s.request.id, i]));
  const missing = plan.stops.filter((s) => !s.chosen);
  const checkpoints = plan.timeline.filter((r) => r.kind === "stop").length;
  const rows = plan.timeline.filter((r) => r.kind !== "prayer" || showPrayers);
  const hasPrayers = plan.timeline.some((r) => r.kind === "prayer");
  return (
    <section aria-label="Quest log">
      <h3 className="mb-2 flex items-center gap-2 font-display text-[13px] font-semibold uppercase tracking-[0.16em] text-slate-300">
        <span aria-hidden>🧭</span> Quest log
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] tracking-wider text-slate-400 ring-1 ring-white/10">
          {checkpoints} checkpoint{checkpoints === 1 ? "" : "s"}
        </span>
        {hasPrayers && onTogglePrayers && (
          <button
            type="button"
            onClick={onTogglePrayers}
            aria-pressed={showPrayers}
            title="Show the five daily Muslim prayer times along your route"
            className={`ml-auto rounded-full px-2.5 py-0.5 font-sans text-[10px] font-semibold normal-case tracking-normal ring-1 transition ${
              showPrayers ? "bg-amber-300/15 text-amber-200 ring-amber-300/40" : "bg-white/5 text-slate-400 ring-white/10 hover:text-slate-200"
            }`}
          >
            🕌 Prayer times {showPrayers ? "on" : "off"}
          </button>
        )}
      </h3>
      <div className="relative">
        {/* the path */}
        <span
          aria-hidden
          className="absolute bottom-6 left-[73px] top-6 w-1 -translate-x-[1px] rounded-full bg-gradient-to-b from-emerald-400 via-brand-300 to-rose-400 opacity-80 shadow-[0_0_12px_rgba(52,207,174,0.6)]"
        />
        <ol className="relative space-y-1.5">
          {rows.map((row, k) => {
            const delay = { animationDelay: `${80 + k * 70}ms` };
            const time = <span className="w-12 shrink-0 pt-1 text-right font-mono text-[13px] font-semibold text-slate-400">{fmtTime(row.time)}</span>;
            if (row.kind === "depart" || row.kind === "arrive") {
              const dep = row.kind === "depart";
              return (
                <li key={k} className="flex animate-fade-up items-start gap-3 py-1.5" style={delay}>
                  {time}
                  <span
                    className={`relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-white/90 font-display text-[11px] font-bold text-white ${
                      dep ? "bg-emerald-500 shadow-[0_0_14px_rgba(52,211,153,0.8)]" : "bg-rose-500 shadow-[0_0_14px_rgba(244,114,182,0.8)]"
                    }`}
                  >
                    {dep ? "A" : "🏁"}
                  </span>
                  <div className="min-w-0 pt-0.5">
                    <p className="font-display text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{dep ? "Start" : "Finish"}</p>
                    <p className="truncate text-sm font-bold text-white">{row.label}</p>
                  </div>
                </li>
              );
            }
            if (row.kind === "prayer") {
              const p = plan.prayer_times.find((x) => x.name === row.prayer);
              return (
                <li key={k} className="animate-fade-up" style={delay}>
                  <div className="flex items-start gap-3 rounded-2xl bg-gradient-to-r from-amber-400/15 to-transparent py-2 pr-2 ring-1 ring-amber-300/20">
                    {time}
                    <span className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#1f1606] text-sm ring-2 ring-amber-300 shadow-[0_0_12px_rgba(251,191,36,0.6)]">
                      🕌
                    </span>
                    <div className="flex-1 text-sm text-amber-100">
                      <b className="font-display tracking-wide">{PRAYER_LABEL[row.prayer ?? ""] ?? row.label}</b> begins
                      {p?.route_fraction != null && <span className="text-amber-200/60"> · {Math.round(p.route_fraction * 100)}% of the way</span>}
                      {!row.stop_id && (
                        <button
                          type="button"
                          className="mt-1 block rounded-full bg-amber-300/15 px-2.5 py-0.5 text-xs font-semibold text-amber-200 ring-1 ring-amber-300/30 transition hover:-translate-y-0.5 hover:bg-amber-300/25"
                          onClick={() => onSuggestMosque(row.prayer!)}
                        >
                          + add a mosque here
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            }
            const idx = stopIndex.get(row.stop_id!) ?? 0;
            const sp = plan.stops[idx];
            const c = sp.chosen!;
            const selected = selectedStopId === sp.request.id;
            return (
              <li key={k} className="animate-fade-up" style={delay}>
                <button
                  type="button"
                  onClick={() => onSelectStop(selected ? null : sp.request.id)}
                  aria-expanded={selected}
                  className={`group flex w-full items-start gap-3 rounded-2xl py-2 pr-2 text-left transition duration-200 ${
                    selected ? "bg-white/[0.08] ring-1 ring-amber-300/40" : "hover:bg-white/[0.05]"
                  }`}
                >
                  {time}
                  <span
                    className={`hex relative z-10 flex h-7 w-8 shrink-0 items-center justify-center bg-gradient-to-br font-display text-[12px] font-bold text-ink-950 transition group-hover:scale-110 ${
                      selected ? "from-amber-200 to-orange-500" : gradFor(sp.request.category)
                    }`}
                  >
                    {idx + 1}
                  </span>
                  <div className="min-w-0 flex-1 text-sm">
                    <div className="text-xs font-medium text-slate-400">
                      {sp.request.icon} {sp.request.label}
                      {sp.request.constraints.dietary.length > 0 && <span className="capitalize text-emerald-300"> · {sp.request.constraints.dietary.join("/")}</span>}
                      {(sp.request.constraints.cuisine ?? []).length > 0 && (
                        <span className="capitalize text-orange-300"> · {sp.request.constraints.cuisine!.join("/").replace(/_/g, " ")}</span>
                      )}
                    </div>
                    <div className="truncate font-bold text-white">
                      {c.name ?? "Unnamed place"}
                      {c.parent?.name && <span className="font-medium text-slate-400"> · {c.parent.name}</span>}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {sp.covered_by ? (
                        <span className="badge bg-violet-400/20 font-display tracking-wide text-violet-200">⚡ COMBO · +0 min</span>
                      ) : (
                        <span className="badge bg-brand-400/15 text-brand-200">
                          ⏱ {fmtAdded(addedMin(c))}
                          {!c.detour_exact && " est."}
                        </span>
                      )}
                      <OpenBadge state={c.open_at_eta} />
                      {(c.kind === "container" || c.kind === "same_poi") && !sp.covered_by && (
                        <span className="badge bg-violet-400/15 text-violet-200">⚡ combined</span>
                      )}
                      {c.hop_off && <span className="badge bg-sky-400/15 text-sky-200">🚏 {c.hop_off}</span>}
                      {c.evidence.some((e) => e.text.startsWith("no ")) && <span className="badge bg-amber-400/15 text-amber-200">unverified</span>}
                      {sp.candidates.length > 1 && (
                        <span className="ml-auto text-[11px] font-semibold text-brand-300">
                          {selected ? "hide" : `${sp.candidates.length - 1} more`}{" "}
                          <span className={`inline-block transition-transform ${selected ? "rotate-180" : ""}`}>▾</span>
                        </span>
                      )}
                    </div>
                    {sp.warnings.map((w) => (
                      <p key={w} className="mt-1.5 text-xs text-amber-300">
                        ⚠ {w}
                      </p>
                    ))}
                  </div>
                </button>
                {selected && <div className="relative z-10 ml-[60px] mt-2 animate-slide-down rounded-2xl bg-ink-900">{renderDetail(sp.request.id)}</div>}
              </li>
            );
          })}
        </ol>
      </div>
      {missing.map((s) => (
        <div key={s.request.id} className="mt-3 animate-fade-up rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-400/25">
          💀 {s.request.icon} <b>{s.request.label}</b> — nothing suitable found along the way.
          {s.warnings.map((w) => (
            <span key={w} className="mt-0.5 block text-xs text-rose-300/80">
              {w}
            </span>
          ))}
        </div>
      ))}
    </section>
  );
}
