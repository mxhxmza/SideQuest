import { useEffect, useState } from "react";
import { BADGES, levelOf, type GameStats } from "../../lib/game";
import { fmtDay } from "../../lib/format";

interface Props {
  open: boolean;
  onClose: () => void;
  stats: GameStats;
  onReset: () => void;
}

export default function TrophyRoom({ open, onClose, stats, onReset }: Props) {
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    if (!open) return;
    setConfirm(false);
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  const lv = levelOf(stats.xp);
  const got = BADGES.filter((b) => stats.badges[b.id]).length;

  return (
    <div className="fixed inset-0 z-[65] flex animate-fade-in items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Trophy room"
        className="panel scroll-soft max-h-[88vh] w-full max-w-xl animate-pop overflow-y-auto rounded-3xl p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-logo text-xl text-gold">🏆 Trophy room</h2>
          <button type="button" onClick={onClose} className="btn-ghost h-8 w-8" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="mb-4 flex items-center gap-3 rounded-2xl bg-gradient-to-r from-amber-500/15 to-transparent p-3 ring-1 ring-amber-300/20">
          <div className="hex flex h-14 w-16 shrink-0 flex-col items-center justify-center bg-gradient-to-br from-amber-200 via-amber-400 to-orange-500 text-ink-950">
            <span className="font-display text-[9px] font-bold tracking-widest">LEVEL</span>
            <span className="font-logo text-xl leading-none">{lv.level}</span>
          </div>
          <div>
            <p className="font-display text-lg font-bold text-white">{lv.rank}</p>
            <p className="text-xs text-slate-400">
              {stats.xp.toLocaleString()} XP total · {lv.need - lv.into} XP to level {lv.level + 1}
            </p>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["🗺️", stats.trips, "trips planned"],
            ["✅", stats.cleared, "side quests"],
            ["⭐", stats.perfect, "perfect runs"],
            ["🏅", `${got}/${BADGES.length}`, "badges"],
          ].map(([i, v, l]) => (
            <div key={String(l)} className="rounded-2xl bg-white/5 px-3 py-2.5 text-center ring-1 ring-white/10">
              <p className="font-display text-xl font-bold text-white">
                <span aria-hidden className="mr-1 text-base">
                  {i}
                </span>
                {v}
              </p>
              <p className="text-[10px] uppercase tracking-wider text-slate-400">{l}</p>
            </div>
          ))}
        </div>

        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {BADGES.map((b, i) => {
            const when = stats.badges[b.id];
            return (
              <li
                key={b.id}
                className={`flex animate-fade-up items-center gap-3 rounded-2xl p-2.5 ring-1 ${
                  when ? "bg-white/[0.07] ring-amber-300/25" : "bg-white/[0.02] ring-white/5"
                }`}
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <span
                  className={`hex flex h-11 w-12 shrink-0 items-center justify-center text-xl ${
                    when ? "bg-gradient-to-br from-amber-200 via-amber-400 to-orange-500" : "bg-white/10 grayscale"
                  }`}
                >
                  {when ? b.icon : "🔒"}
                </span>
                <div className="min-w-0">
                  <p className={`font-display font-semibold ${when ? "text-white" : "text-slate-400"}`}>{b.name}</p>
                  <p className="text-xs text-slate-400">{b.desc}</p>
                  {when && <p className="text-[10px] text-amber-300/80">Unlocked {fmtDay(when)}</p>}
                </div>
              </li>
            );
          })}
        </ul>

        <div className="mt-5 flex items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs text-slate-500">
          <span>Progress is saved in this browser only.</span>
          {confirm ? (
            <span className="flex gap-2">
              <button type="button" className="font-semibold text-slate-300 hover:underline" onClick={() => setConfirm(false)}>
                Keep
              </button>
              <button
                type="button"
                className="font-semibold text-rose-400 hover:underline"
                onClick={() => {
                  onReset();
                  setConfirm(false);
                }}
              >
                Yes, reset
              </button>
            </span>
          ) : (
            <button type="button" className="font-semibold text-slate-400 hover:text-rose-400" onClick={() => setConfirm(true)}>
              Reset progress
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
