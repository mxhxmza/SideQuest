import type { Mode } from "../types";

export const MODES: { key: Mode; icon: string; label: string }[] = [
  { key: "drive", icon: "🚗", label: "Drive" },
  { key: "transit", icon: "🚇", label: "Transit" },
  { key: "walk", icon: "🚶", label: "Walk" },
  { key: "cycle", icon: "🚲", label: "Cycle" },
];

/** Segmented control with a sliding highlight. */
export default function ModeSwitch({ value, onChange }: { value: Mode; onChange: (m: Mode) => void }) {
  const idx = Math.max(0, MODES.findIndex((m) => m.key === value));
  return (
    <div className="relative grid grid-cols-4 rounded-2xl bg-slate-100 p-1" role="radiogroup" aria-label="Travel mode">
      <span
        aria-hidden
        className="absolute inset-y-1 left-1 rounded-xl bg-white shadow-md shadow-slate-300/60 transition-transform duration-300 ease-[cubic-bezier(0.34,1.4,0.64,1)]"
        style={{ width: "calc((100% - 0.5rem) / 4)", transform: `translateX(${idx * 100}%)` }}
      />
      {MODES.map((m) => (
        <button
          key={m.key}
          type="button"
          role="radio"
          aria-checked={value === m.key}
          onClick={() => onChange(m.key)}
          className={`relative z-10 flex flex-col items-center gap-0.5 rounded-xl py-2 text-[11px] font-semibold transition-colors ${
            value === m.key ? "text-brand-700" : "text-slate-500 hover:text-slate-700"
          }`}
        >
          <span className={`text-lg transition-transform duration-300 ${value === m.key ? "scale-110" : ""}`} aria-hidden>
            {m.icon}
          </span>
          {m.label}
        </button>
      ))}
    </div>
  );
}
