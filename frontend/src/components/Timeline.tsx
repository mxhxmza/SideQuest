import type { ReactNode } from "react";
import type { PlaceCandidate, TripPlan } from "../types";
import { addedMin, fmtAdded, fmtTime, PRAYER_LABEL } from "../lib/format";

interface Props {
  plan: TripPlan;
  selectedStopId: string | null;
  onSelectStop: (id: string | null) => void;
  onSuggestMosque: (prayer: string) => void;
  renderDetail: (stopId: string) => ReactNode;
}

export function OpenBadge({ state }: { state: PlaceCandidate["open_at_eta"] }) {
  if (state === true) return <span className="badge bg-emerald-100 text-emerald-700">● open</span>;
  if (state === false) return <span className="badge bg-rose-100 text-rose-700">● closed</span>;
  return <span className="badge bg-slate-100 text-slate-500">hours unknown</span>;
}

const KIND_STYLE: Record<string, string> = {
  meal: "from-orange-400 to-rose-500",
  prayer: "from-amber-400 to-orange-500",
  search: "from-violet-400 to-fuchsia-500",
  default: "from-brand-400 to-cyan-500",
};

export default function Timeline({ plan, selectedStopId, onSelectStop, onSuggestMosque, renderDetail }: Props) {
  const stopIndex = new Map(plan.stops.map((s, i) => [s.request.id, i]));
  const missing = plan.stops.filter((s) => !s.chosen);
  return (
    <div className="relative">
      {/* spine */}
      <span aria-hidden className="absolute bottom-6 left-[73px] top-6 w-0.5 rounded bg-gradient-to-b from-emerald-400 via-brand-300 to-rose-400" />
      <ol className="relative space-y-1.5">
        {plan.timeline.map((row, k) => {
          const delay = { animationDelay: `${80 + k * 70}ms` };
          const time = (
            <span className="w-12 shrink-0 pt-1 text-right font-mono text-[13px] font-semibold text-slate-500">
              {fmtTime(row.time)}
            </span>
          );
          if (row.kind === "depart" || row.kind === "arrive") {
            const dep = row.kind === "depart";
            return (
              <li key={k} className="flex animate-fade-up items-start gap-3 py-1.5" style={delay}>
                {time}
                <span
                  className={`relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-[3px] border-white text-[10px] font-extrabold text-white shadow ${
                    dep ? "bg-emerald-500" : "bg-rose-500"
                  }`}
                >
                  {dep ? "A" : "B"}
                </span>
                <div className="pt-0.5 text-sm font-bold text-slate-800">{row.label}</div>
              </li>
            );
          }
          if (row.kind === "prayer") {
            const p = plan.prayer_times.find((x) => x.name === row.prayer);
            return (
              <li key={k} className="animate-fade-up" style={delay}>
                <div className="flex items-start gap-3 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50/40 py-2 pr-2 ring-1 ring-amber-200/70">
                  {time}
                  <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 text-sm ring-2 ring-white">
                    🕌
                  </span>
                  <div className="flex-1 text-sm text-amber-900">
                    <b>{PRAYER_LABEL[row.prayer ?? ""] ?? row.label}</b> begins
                    {p?.route_fraction != null && (
                      <span className="text-amber-800/70"> · {Math.round(p.route_fraction * 100)}% of the way</span>
                    )}
                    {!row.stop_id && (
                      <button
                        type="button"
                        className="mt-1 block rounded-full bg-white px-2.5 py-0.5 text-xs font-semibold text-amber-800 shadow-sm ring-1 ring-amber-200 transition hover:-translate-y-0.5 hover:bg-amber-100"
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
          const grad = KIND_STYLE[sp.request.category === "keyword" ? "search" : ""] ??
            (["meal", "hawker", "cafe", "ice_cream"].includes(sp.request.category)
              ? KIND_STYLE.meal
              : ["mosque", "prayer_room"].includes(sp.request.category)
                ? KIND_STYLE.prayer
                : KIND_STYLE.default);
          return (
            <li key={k} className="animate-fade-up" style={delay}>
              <button
                type="button"
                onClick={() => onSelectStop(selected ? null : sp.request.id)}
                aria-expanded={selected}
                className={`group flex w-full items-start gap-3 rounded-2xl py-2 pr-2 text-left transition duration-200 ${
                  selected ? "bg-white shadow-lg ring-1 ring-brand-200" : "hover:bg-white hover:shadow-md"
                }`}
              >
                {time}
                <span
                  className={`relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${grad} text-[11px] font-extrabold text-white shadow ring-2 ring-white transition group-hover:scale-110`}
                >
                  {idx + 1}
                </span>
                <div className="min-w-0 flex-1 text-sm">
                  <div className="text-xs font-medium text-slate-500">
                    {sp.request.icon} {sp.request.label}
                    {sp.request.constraints.dietary.length > 0 && (
                      <span className="capitalize text-emerald-700"> · {sp.request.constraints.dietary.join("/")}</span>
                    )}
                  </div>
                  <div className="truncate font-bold text-slate-900">
                    {c.name ?? "Unnamed place"}
                    {c.parent?.name && <span className="font-medium text-slate-500"> · {c.parent.name}</span>}
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {sp.covered_by ? (
                      <span className="badge bg-violet-100 text-violet-700">★ same stop · +0 min</span>
                    ) : (
                      <span className="badge bg-brand-100 text-brand-800">
                        {fmtAdded(addedMin(c))}
                        {!c.detour_exact && " est."}
                      </span>
                    )}
                    <OpenBadge state={c.open_at_eta} />
                    {(c.kind === "container" || c.kind === "same_poi") && (
                      <span className="badge bg-violet-100 text-violet-700">★ combined</span>
                    )}
                    {c.hop_off && <span className="badge bg-sky-100 text-sky-700">🚏 {c.hop_off}</span>}
                    {c.evidence.some((e) => e.text.startsWith("no ")) && (
                      <span className="badge bg-amber-100 text-amber-800">unverified</span>
                    )}
                    {sp.candidates.length > 1 && (
                      <span className="ml-auto text-[11px] font-semibold text-brand-600">
                        {selected ? "hide" : `${sp.candidates.length - 1} more`}{" "}
                        <span className={`inline-block transition-transform ${selected ? "rotate-180" : ""}`}>▾</span>
                      </span>
                    )}
                  </div>
                  {sp.warnings.map((w) => (
                    <p key={w} className="mt-1.5 text-xs text-amber-700">
                      ⚠ {w}
                    </p>
                  ))}
                </div>
              </button>
              {selected && <div className="ml-[60px] mt-2 animate-slide-down">{renderDetail(sp.request.id)}</div>}
            </li>
          );
        })}
      </ol>
      {missing.map((s) => (
        <div key={s.request.id} className="mt-3 animate-fade-up rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-200">
          {s.request.icon} <b>{s.request.label}</b> — nothing suitable found along the way.
          {s.warnings.map((w) => (
            <span key={w} className="mt-0.5 block text-xs text-rose-700/80">
              {w}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
