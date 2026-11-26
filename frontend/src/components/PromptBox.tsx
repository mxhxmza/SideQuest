import { useEffect, useState } from "react";
import type { Category, Cuisine, StopRequest } from "../types";
import StopChips from "./StopChips";

const EXAMPLES = [
  "Italian dinner around 7pm, then petrol and a pharmacy",
  "church before 10am, then a coffee",
  "Hindu temple, then a vegetarian lunch",
  "mosque at Asr, then a halal restaurant",
  "Buddhist temple and Japanese food around 1pm",
  "coffee 45 min in, then an ATM and a toilet",
  "gurdwara, then Korean BBQ",
];

const QUICK = [
  { icon: "🍝", text: "Italian dinner" },
  { icon: "🍣", text: "sushi" },
  { icon: "⛪", text: "church" },
  { icon: "🛕", text: "temple" },
  { icon: "🕌", text: "mosque at Asr" },
  { icon: "🥗", text: "vegetarian lunch" },
  { icon: "☕", text: "coffee" },
  { icon: "⛽", text: "petrol" },
  { icon: "💊", text: "pharmacy" },
];

interface Props {
  text: string;
  onText: (t: string) => void;
  stops: StopRequest[];
  onStops: (s: StopRequest[]) => void;
  unrecognized: string[];
  categories: Category[];
  cuisines: Cuisine[];
  parsing: boolean;
}

export default function PromptBox({ text, onText, stops, onStops, unrecognized, categories, cuisines, parsing }: Props) {
  const [focused, setFocused] = useState(false);
  const [ex, setEx] = useState(0);

  // rotate the placeholder through examples while the box is empty
  useEffect(() => {
    if (text) return;
    const t = setInterval(() => setEx((i) => (i + 1) % EXAMPLES.length), 3500);
    return () => clearInterval(t);
  }, [text]);

  const append = (phrase: string) => onText(text.trim() ? `${text.trim().replace(/[,.]$/, "")}, ${phrase}` : phrase);

  return (
    <div>
      <label htmlFor="prompt" className="lbl flex items-center gap-1.5">
        <span aria-hidden>📜</span> Side quests <span className="normal-case tracking-normal text-slate-500">— what do you need on the way?</span>
      </label>
      <div className={`rounded-2xl p-[2px] transition ${focused || text ? "prompt-ring shadow-[0_0_28px_rgba(52,207,174,0.25)]" : "bg-white/10"}`}>
        <div className="relative rounded-[14px] bg-ink-950">
          <textarea
            id="prompt"
            className="block min-h-24 w-full resize-none rounded-[14px] bg-transparent px-4 pb-3 pt-3 text-[15px] leading-relaxed text-slate-100 outline-none"
            value={text}
            onChange={(e) => onText(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
          />
          {!text && (
            <span key={ex} className="pointer-events-none absolute left-4 right-4 top-3 animate-fade-up text-[15px] leading-relaxed text-slate-500">
              e.g. {EXAMPLES[ex]}
              <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-blink bg-brand-300" />
            </span>
          )}
          {parsing && (
            <span className="absolute bottom-2 right-3 flex gap-1" aria-label="Reading">
              {[0, 1, 2].map((i) => (
                <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-300" style={{ animationDelay: `${i * 120}ms` }} />
              ))}
            </span>
          )}
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {QUICK.map((q, i) => (
          <button
            key={q.text}
            type="button"
            onClick={() => append(q.text)}
            className="animate-fade-up rounded-full bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300 ring-1 ring-white/10 transition hover:-translate-y-0.5 hover:bg-brand-400/15 hover:text-brand-200 hover:ring-brand-400/40"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <span aria-hidden>{q.icon}</span> {q.text}
          </button>
        ))}
      </div>

      {(stops.length > 0 || unrecognized.length > 0) && (
        <div className="mt-4 animate-fade-up rounded-2xl bg-gradient-to-br from-brand-400/10 via-cyan-400/5 to-violet-400/10 p-3 ring-1 ring-brand-300/20">
          <p className="mb-2 flex items-center gap-1.5 font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-brand-200">
            <span aria-hidden>✨</span> Quest log · {stops.length}
            <span className="font-sans font-medium normal-case tracking-normal text-slate-400">· tap one to tweak it</span>
          </p>
          <StopChips stops={stops} categories={categories} cuisines={cuisines} onChange={onStops} />
          {unrecognized.map((u) => (
            <p key={u} className="mt-2 animate-pop text-xs text-amber-300">
              🤔 Didn't understand “{u}” — try naming the place or thing, e.g. “church”, “sushi”, “ATM”.
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
