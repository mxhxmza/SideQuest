import { useSeen } from "../../lib/useReveal";

type Term = { label: string; v: number; color: string };

/** Illustrative candidates for one stop ("Italian dinner"); penalty values are the planner's real ones. */
const CANDS: { name: string; note: string; terms: Term[] }[] = [
  {
    name: "Trattoria, two streets away",
    note: "tagged cuisine=italian · open when you'd arrive",
    terms: [{ label: "Detour", v: 4, color: "bg-brand-400" }],
  },
  {
    name: "Pizza place, right on the route",
    note: "Italian only by its name · opening hours not mapped",
    terms: [
      { label: "Detour", v: 0.5, color: "bg-brand-400" },
      { label: "Matched by name only", v: 2, color: "bg-amber-400" },
      { label: "Hours unknown", v: 3, color: "bg-slate-400" },
    ],
  },
  {
    name: "Osteria by the exit",
    note: "tagged cuisine=italian · closed when you'd arrive",
    terms: [
      { label: "Detour", v: 1, color: "bg-brand-400" },
      { label: "Closed at ETA", v: 60, color: "bg-rose-500" },
    ],
  },
];

const SCALE = 14; // minutes shown at full bar width

export const RULES: [string, string][] = [
  ["Detour", "real extra minutes, verified by routing"],
  ["Waiting", "minutes waiting for a prayer time to begin (mosque stops)"],
  ["Closed at your ETA", "+60"],
  ["Opening hours unknown", "+3"],
  ["Outside the time window", "+0.5 per minute outside"],
  ["Pushes later stops late", "+0.5 per minute"],
  ["Weak dietary evidence (halal, veg…)", "+5"],
  ["Category or cuisine only in the name", "+2"],
  ["Place has no name", "+2"],
  ["Off the target time", "+0.1 per minute (tie-breaker)"],
  ["Combo with another stop", "bonus, subtracted"],
];

export default function ScoreDemo() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  return (
    <div ref={ref} className="space-y-3">
      {CANDS.map((c, i) => {
        const total = c.terms.reduce((n, t) => n + t.v, 0);
        const win = i === 0;
        let acc = 0;
        return (
          <div
            key={c.name}
            className={`rounded-2xl p-4 ring-1 transition ${win ? "bg-amber-300/[0.07] ring-amber-300/40" : "bg-white/[0.03] ring-white/10"}`}
          >
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-display font-semibold text-white">
                  <span className="mr-1.5 text-slate-500">#{i + 1}</span>
                  {c.name}
                </p>
                <p className="text-xs text-slate-400">{c.note}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className={`font-display text-2xl font-bold leading-none ${win ? "text-amber-300" : "text-slate-200"}`}>{total.toFixed(1)}</p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">score</p>
              </div>
            </div>
            <div className="relative flex h-4 overflow-hidden rounded-full bg-black/40">
              {c.terms.map((t, k) => {
                const left = Math.min(100, (acc / SCALE) * 100);
                const w = Math.max(0, Math.min(100 - left, (t.v / SCALE) * 100));
                acc += t.v;
                return (
                  <span
                    key={t.label}
                    className={`h-full ${t.color} transition-[width] duration-1000 ease-out ${k ? "border-l-2 border-ink-950" : ""}`}
                    style={{ width: seen ? `${w}%` : "0%", transitionDelay: `${i * 250 + k * 200}ms` }}
                    title={`${t.label}: +${t.v}`}
                  />
                );
              })}
              {total > SCALE && (
                <span className="absolute inset-y-0 right-1.5 flex items-center font-display text-[10px] font-bold text-white drop-shadow">⟫⟫</span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-400">
              {c.terms.map((t) => (
                <span key={t.label} className="flex items-center gap-1">
                  <span className={`h-2 w-2 rounded-full ${t.color}`} />
                  {t.label} +{t.v}
                </span>
              ))}
              {win && <span className="ml-auto font-display font-semibold tracking-wide text-amber-300">★ CHOSEN</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
