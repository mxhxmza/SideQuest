import { useEffect, useState } from "react";
import type { Category, StopRequest } from "../types";
import StopChips from "./StopChips";

const EXAMPLES = [
  "halal lunch around 1pm, a mosque near Asr time, somewhere to buy a phone charger",
  "mosque to pray Asr, a halal shop to buy ice cream along the way",
  "coffee 45 min in, then petrol and a toilet",
  "vegetarian dinner at 7pm and a pharmacy",
  "pray Zohor, then grab bubble tea",
];

const QUICK = [
  { icon: "🍽", text: "halal lunch around 1pm" },
  { icon: "🕌", text: "mosque at Asr" },
  { icon: "🍨", text: "ice cream" },
  { icon: "☕", text: "coffee" },
  { icon: "⛽", text: "petrol" },
  { icon: "🚻", text: "toilet" },
];

interface Props {
  text: string;
  onText: (t: string) => void;
  stops: StopRequest[];
  onStops: (s: StopRequest[]) => void;
  unrecognized: string[];
  categories: Category[];
  parsing: boolean;
}

export default function PromptBox({ text, onText, stops, onStops, unrecognized, categories, parsing }: Props) {
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
      <label htmlFor="prompt" className="lbl">
        What do you need along the way?
      </label>
      <div className={`rounded-2xl p-[2px] transition ${focused ? "prompt-ring shadow-lg shadow-brand-500/20" : "bg-slate-200"}`}>
        <div className="relative rounded-[14px] bg-white">
          <textarea
            id="prompt"
            className="block min-h-24 w-full resize-none rounded-[14px] bg-transparent px-4 pb-3 pt-3 text-[15px] leading-relaxed text-slate-900 outline-none"
            value={text}
            onChange={(e) => onText(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
          />
          {!text && (
            <span
              key={ex}
              className="pointer-events-none absolute left-4 right-4 top-3 animate-fade-up text-[15px] leading-relaxed text-slate-400"
            >
              e.g. {EXAMPLES[ex]}
            </span>
          )}
          {parsing && (
            <span className="absolute bottom-2 right-3 flex gap-1" aria-label="Reading">
              {[0, 1, 2].map((i) => (
                <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-400" style={{ animationDelay: `${i * 120}ms` }} />
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
            className="animate-fade-up rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:-translate-y-0.5 hover:bg-brand-50 hover:text-brand-700"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <span aria-hidden>{q.icon}</span> {q.text}
          </button>
        ))}
      </div>

      {(stops.length > 0 || unrecognized.length > 0) && (
        <div className="mt-4 animate-fade-up rounded-2xl border border-brand-100 bg-gradient-to-br from-brand-50/80 to-cyan-50/60 p-3">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-brand-700">
            <span aria-hidden>✨</span> I'll look for
            <span className="font-medium normal-case tracking-normal text-brand-600/70">· tap a stop to adjust</span>
          </p>
          <StopChips stops={stops} categories={categories} onChange={onStops} />
          {unrecognized.map((u) => (
            <p key={u} className="mt-2 animate-pop text-xs text-amber-700">
              🤔 Didn't understand “{u}” — try naming the place or thing, e.g. “ice cream”, “ATM”.
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
