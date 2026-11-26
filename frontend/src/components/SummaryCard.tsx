import type { TripPlan } from "../types";
import { fmtAdded, fmtDistance, fmtDuration, fmtTime } from "../lib/format";
import { MODES } from "./ModeSwitch";

export default function SummaryCard({ plan }: { plan: TripPlan }) {
  const found = plan.stops.filter((s) => s.chosen).length;
  const mode = MODES.find((m) => m.key === plan.route.mode);
  return (
    <div className="animate-fade-up">
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 via-brand-500 to-cyan-500 bg-[length:200%_200%] p-5 text-white shadow-xl shadow-brand-600/25 animate-gradient">
      <div aria-hidden className="absolute -right-8 -top-10 h-36 w-36 rounded-full bg-white/10 blur-sm animate-float" />
      <div aria-hidden className="absolute -bottom-12 right-16 h-28 w-28 rounded-full bg-white/10" />
      <div className="relative flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-white/75">Arrive</p>
          <p className="text-4xl font-extrabold leading-none tracking-tight">{fmtTime(plan.arrival_eta)}</p>
          <p className="mt-1 text-xs text-white/80">
            leave {fmtTime(plan.departure_time)} · {mode?.icon} {mode?.label}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-extrabold leading-none">{fmtAdded(plan.total_added_min)}</p>
          <p className="text-xs text-white/80">for detours</p>
        </div>
      </div>
      <div className="relative mt-4 grid grid-cols-3 gap-2 text-center">
        {[
          { v: `${found}/${plan.stops.length}`, l: "stops found" },
          { v: fmtDuration(plan.route.duration_s), l: "base trip" },
          { v: fmtDistance(plan.route.distance_m), l: "distance" },
        ].map((x) => (
          <div key={x.l} className="rounded-2xl bg-white/15 px-2 py-2 backdrop-blur-sm">
            <p className="text-sm font-bold">{x.v}</p>
            <p className="text-[10px] uppercase tracking-wide text-white/75">{x.l}</p>
          </div>
        ))}
      </div>
    </div>
    </div>
  );
}
