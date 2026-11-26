import { useEffect, useState } from "react";

const STEPS = [
  { icon: "🧠", text: "Reading your side quests" },
  { icon: "🛣️", text: "Plotting the main route" },
  { icon: "📍", text: "Scouting places along the way" },
  { icon: "⏱️", text: "Checking real detour times" },
];

const TIPS = [
  "Say “Italian”, “sushi” or “dim sum” and only matching restaurants are picked.",
  "Add “halal”, “vegetarian” or “vegan” to any food stop.",
  "Churches, temples, mosques, gurdwaras — just name the place of worship.",
  "Tap a checkpoint to see the other options — and why they rank lower.",
  "Two quests in the same mall cost zero extra minutes. That's a combo!",
  "“coffee 45 min in” times a stop by trip progress, not the clock.",
  "≤ 5 extra minutes per stop earns 3 stars.",
  "Pin an alternative with “Use this” and the rest of the trip re-plans.",
];

/** Over the map while a plan is computed. The steps are the planner's real phases;
 * they advance on a timer because the server answers in one response. */
export default function PlanningOverlay() {
  const [step, setStep] = useState(0);
  const [tip] = useState(() => Math.floor(Math.random() * TIPS.length));
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    return () => clearInterval(t);
  }, []);
  const pct = ((step + 1) / STEPS.length) * 92;
  return (
    <div className="absolute inset-0 z-20 flex animate-fade-in items-center justify-center bg-ink-950/50 p-4 backdrop-blur-[3px]">
      <div className="panel w-full max-w-sm animate-pop rounded-3xl px-6 py-5 shadow-2xl shadow-black/60">
        <p className="text-center font-logo text-lg tracking-wider text-gradient">
          Loading level<span className="animate-blink">…</span>
        </p>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-black/50 ring-1 ring-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-brand-400 via-cyan-400 to-violet-400 shadow-[0_0_14px_rgba(52,207,174,0.7)] transition-[width] duration-700 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        <ol className="mt-4 space-y-1.5">
          {STEPS.map((s, i) => (
            <li
              key={s.text}
              className={`flex items-center gap-2 text-sm transition-all duration-500 ${
                i < step ? "text-slate-500" : i === step ? "font-semibold text-white" : "text-slate-600"
              }`}
            >
              <span className="w-5 text-center" aria-hidden>
                {i < step ? <span className="text-brand-300">✓</span> : s.icon}
              </span>
              {s.text}
              {i === step && <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-300" />}
            </li>
          ))}
        </ol>
        <p className="mt-4 rounded-xl bg-white/5 px-3 py-2 text-xs text-slate-400 ring-1 ring-white/10">
          <span className="font-display font-semibold tracking-wider text-amber-300">TIP</span> {TIPS[tip]}
        </p>
      </div>
    </div>
  );
}
