import { BADGES, levelOf, type GameStats } from "../../lib/game";

interface Props {
  stats: GameStats;
  sound: boolean;
  onSound: (on: boolean) => void;
  onTrophies: () => void;
}

/** Player HUD: level, XP bar, trophies, sound. */
export default function Hud({ stats, sound, onSound, onTrophies }: Props) {
  const lv = levelOf(stats.xp);
  const pct = (lv.into / lv.need) * 100;
  const count = BADGES.filter((b) => stats.badges[b.id]).length;
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-black/30 p-2 ring-1 ring-white/10">
      <div
        className="hex flex h-10 w-11 shrink-0 flex-col items-center justify-center bg-gradient-to-br from-amber-200 via-amber-400 to-orange-500 text-ink-950"
        title={`Level ${lv.level} · ${stats.xp} XP total`}
      >
        <span className="font-display text-[8px] font-bold leading-none tracking-widest">LV</span>
        <span key={lv.level} className="animate-pop font-logo text-[15px] leading-none">
          {lv.level}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-baseline justify-between gap-2 text-[11px]">
          <span className="truncate font-display font-semibold uppercase tracking-wider text-amber-200">{lv.rank}</span>
          <span className="shrink-0 font-mono text-slate-400">
            {lv.into}/{lv.need} XP
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-black/50 ring-1 ring-white/5" role="progressbar" aria-valuenow={lv.into} aria-valuemax={lv.need} aria-label="XP to next level">
          <div className="xp-fill h-full rounded-full transition-[width] duration-1000 ease-out" style={{ width: `${Math.max(4, pct)}%` }} />
        </div>
      </div>
      <button
        type="button"
        onClick={onTrophies}
        className="flex shrink-0 items-center gap-1 rounded-xl bg-white/5 px-2.5 py-1.5 font-display text-sm font-semibold text-amber-200 ring-1 ring-white/10 transition hover:-translate-y-0.5 hover:bg-white/10"
        title="Trophy room"
        aria-label={`Trophy room: ${count} of ${BADGES.length} badges`}
      >
        <span aria-hidden>🏆</span>
        {count}
        <span className="text-slate-500">/{BADGES.length}</span>
      </button>
      <button
        type="button"
        onClick={() => onSound(!sound)}
        aria-pressed={sound}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/5 text-sm ring-1 ring-white/10 transition hover:bg-white/10"
        title={sound ? "Sound effects on" : "Sound effects off"}
        aria-label="Sound effects"
      >
        {sound ? "🔊" : "🔇"}
      </button>
    </div>
  );
}
