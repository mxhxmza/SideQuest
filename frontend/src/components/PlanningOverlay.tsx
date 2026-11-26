import { useEffect, useState } from "react";

const STEPS = [
  { icon: "🧠", text: "Reading what you need" },
  { icon: "🛣️", text: "Finding the route" },
  { icon: "📍", text: "Searching places along the way" },
  { icon: "⏱️", text: "Checking real detour times" },
];

/** Shown over the map while a plan is computed. The steps are the planner's real
 * phases; they advance on a timer because the server answers in one response. */
export default function PlanningOverlay() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-900/20 backdrop-blur-[2px]">
      <div className="animate-pop rounded-3xl bg-white/95 px-7 py-6 shadow-2xl ring-1 ring-black/5">
        <div className="relative mx-auto mb-4 h-16 w-16">
          <span className="absolute inset-0 animate-ping-slow rounded-full bg-brand-400/40" />
          <span className="absolute inset-0 animate-ping-slow rounded-full bg-brand-400/30" style={{ animationDelay: "0.7s" }} />
          <span className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-cyan-500 text-2xl shadow-lg">
            🧭
          </span>
        </div>
        <ol className="space-y-1.5">
          {STEPS.map((s, i) => (
            <li
              key={s.text}
              className={`flex items-center gap-2 text-sm transition-all duration-500 ${
                i < step ? "text-slate-400" : i === step ? "font-semibold text-slate-900" : "text-slate-300"
              }`}
            >
              <span className="w-5 text-center" aria-hidden>
                {i < step ? "✓" : s.icon}
              </span>
              {s.text}
              {i === step && <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
