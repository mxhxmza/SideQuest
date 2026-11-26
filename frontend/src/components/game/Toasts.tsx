import { useEffect } from "react";

export interface Toast {
  id: number;
  icon: string;
  kicker: string;
  title: string;
  body?: string;
  tone?: "gold" | "violet" | "brand";
}

const TONE = {
  gold: "from-amber-200 via-amber-400 to-orange-500",
  violet: "from-violet-300 to-fuchsia-500",
  brand: "from-brand-300 to-cyan-500",
};

function ToastItem({ t, onDone }: { t: Toast; onDone: (id: number) => void }) {
  useEffect(() => {
    const k = setTimeout(() => onDone(t.id), 4200);
    return () => clearTimeout(k);
  }, [t.id, onDone]);
  return (
    <div
      role="status"
      className="panel pointer-events-auto flex w-full max-w-sm animate-toast items-center gap-3 rounded-2xl px-3.5 py-3 shadow-2xl shadow-black/50"
    >
      <span className={`hex flex h-11 w-12 shrink-0 animate-wiggle items-center justify-center bg-gradient-to-br text-xl ${TONE[t.tone ?? "gold"]}`}>
        {t.icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300">{t.kicker}</p>
        <p className="truncate font-display text-base font-bold text-white">{t.title}</p>
        {t.body && <p className="truncate text-xs text-slate-400">{t.body}</p>}
      </div>
      <button type="button" onClick={() => onDone(t.id)} className="self-start text-slate-500 hover:text-white" aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}

export default function Toasts({ items, onDone }: { items: Toast[]; onDone: (id: number) => void }) {
  return (
    <div className="pointer-events-none fixed inset-x-0 top-3 z-[70] flex flex-col items-center gap-2 px-4" aria-live="polite">
      {items.map((t) => (
        <ToastItem key={t.id} t={t} onDone={onDone} />
      ))}
    </div>
  );
}
