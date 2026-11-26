import { useEffect, useState } from "react";

/** Real outputs of the rules parser for these sentences (checked against /api/parse). */
const SCRIPTS: { text: string; chips: { icon: string; label: string; diet?: string; cuisine?: string; when: string }[] }[] = [
  {
    text: "church before 10am, then Italian dinner",
    chips: [
      { icon: "⛪", label: "Church", when: "before 10:00" },
      { icon: "🍽", label: "Meal", cuisine: "Italian", when: "~19:00" },
    ],
  },
  {
    text: "Hindu temple, then a vegetarian lunch",
    chips: [
      { icon: "🛕", label: "Hindu temple", when: "any time" },
      { icon: "🍽", label: "Meal", diet: "vegetarian", when: "~12:30" },
    ],
  },
  {
    text: "Buddhist temple and Japanese food around 1pm",
    chips: [
      { icon: "☸️", label: "Buddhist temple", when: "any time" },
      { icon: "🍽", label: "Meal", cuisine: "Japanese", when: "~13:00" },
    ],
  },
  {
    text: "mosque at Asr, then a halal restaurant",
    chips: [
      { icon: "🕌", label: "Mosque", when: "@Asar" },
      { icon: "🍽", label: "Meal", diet: "halal", when: "any time" },
    ],
  },
  {
    text: "coffee 45 min in, then petrol and a toilet",
    chips: [
      { icon: "☕", label: "Café / coffee", when: "45 min in" },
      { icon: "⛽", label: "Petrol station", when: "any time" },
      { icon: "🚻", label: "Toilet", when: "any time" },
    ],
  },
];

type Phase = "typing" | "thinking" | "done";

/** Typewriter demo of plain-English → structured stops. */
export default function PromptDemo({ active }: { active: boolean }) {
  const [i, setI] = useState(0);
  const [n, setN] = useState(0);
  const [phase, setPhase] = useState<Phase>("typing");
  const s = SCRIPTS[i];

  useEffect(() => {
    if (!active) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setN(s.text.length);
      setPhase("done");
      return;
    }
    let t: ReturnType<typeof setTimeout>;
    if (phase === "typing") {
      if (n < s.text.length) t = setTimeout(() => setN(n + 1), 38 + Math.random() * 40);
      else t = setTimeout(() => setPhase("thinking"), 350);
    } else if (phase === "thinking") {
      t = setTimeout(() => setPhase("done"), 700);
    } else {
      t = setTimeout(() => {
        setI((i + 1) % SCRIPTS.length);
        setN(0);
        setPhase("typing");
      }, 3600);
    }
    return () => clearTimeout(t);
  }, [active, phase, n, i, s.text.length]);

  return (
    <div className="panel rounded-3xl p-4 shadow-2xl shadow-black/40 sm:p-5">
      <div className="mb-3 flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-300/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
        <span className="ml-2 font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Side quests</span>
      </div>
      <div className="prompt-ring rounded-2xl p-[2px]">
        <div className="min-h-[84px] rounded-[14px] bg-ink-950 px-4 py-3 text-[15px] leading-relaxed text-slate-100">
          {s.text.slice(0, n)}
          {phase === "typing" && <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-blink bg-brand-300" />}
          {phase === "thinking" && (
            <span className="ml-2 inline-flex gap-1 align-middle" aria-label="Parsing">
              {[0, 1, 2].map((k) => (
                <span key={k} className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-300" style={{ animationDelay: `${k * 120}ms` }} />
              ))}
            </span>
          )}
        </div>
      </div>
      <div className="mt-4 min-h-[112px] rounded-2xl bg-gradient-to-br from-brand-400/10 via-cyan-400/5 to-violet-400/10 p-3 ring-1 ring-brand-300/20">
        <p className="mb-2 font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-brand-200">✨ Quest log</p>
        {phase === "done" ? (
          <div className="flex flex-wrap gap-2">
            {s.chips.map((c, k) => (
              <span key={c.label + i} className="chip animate-pop" style={{ animationDelay: `${k * 110}ms` }}>
                <span className="hex flex h-5 w-6 items-center justify-center bg-gradient-to-br from-brand-300 to-brand-600 font-display text-[10px] font-bold text-ink-950">
                  {k + 1}
                </span>
                <span aria-hidden>{c.icon}</span>
                {c.diet && <span className="font-semibold capitalize text-emerald-300">{c.diet}</span>}
                {c.cuisine && <span className="font-semibold text-orange-300">{c.cuisine}</span>}
                <span className="font-medium text-white">{c.label}</span>
                <span className="text-slate-400">· {c.when}</span>
              </span>
            ))}
          </div>
        ) : (
          <div className="flex gap-2">
            <span className="skeleton h-8 w-32 rounded-full" />
            <span className="skeleton h-8 w-40 rounded-full" />
          </div>
        )}
      </div>
    </div>
  );
}
