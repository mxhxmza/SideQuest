import { useEffect, useState } from "react";
import type { TripPlan } from "../../types";
import { levelOf, scoreRun, type Reward } from "../../lib/game";
import { fmtAdded, fmtDistance, fmtDuration, fmtTime } from "../../lib/format";
import { sfx } from "../../lib/sfx";
import { MODES } from "../ModeSwitch";

const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function useCountUp(target: number, ms: number, delay: number) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (reduced()) {
      setV(target);
      return;
    }
    let raf = 0;
    let start = 0;
    const t = setTimeout(() => {
      const step = (now: number) => {
        start ||= now;
        const p = Math.min(1, (now - start) / ms);
        setV(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, delay);
    return () => {
      clearTimeout(t);
      cancelAnimationFrame(raf);
    };
  }, [target, ms, delay]);
  return v;
}

function Star({ on, i }: { on: boolean; i: number }) {
  const big = i === 1;
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      className={`${big ? "-mb-0 h-16 w-16" : "mb-1 h-12 w-12"} ${on ? "animate-star drop-shadow-[0_0_14px_rgba(251,191,36,0.85)]" : "opacity-40"}`}
      style={{ animationDelay: `${250 + i * 280}ms` }}
    >
      <path
        d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.3l-5.8 3.1 1.1-6.5L2.6 9.3l6.5-.9z"
        fill={on ? "url(#qc-gold)" : "rgba(255,255,255,0.08)"}
        stroke={on ? "#fef3c7" : "rgba(255,255,255,0.25)"}
        strokeWidth="0.9"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** End-of-run screen: stars, the real trip numbers, XP and new badges. */
export default function QuestComplete({ plan, reward }: { plan: TripPlan; reward: Reward | null }) {
  const run = reward?.run ?? scoreRun(plan);
  const mode = MODES.find((m) => m.key === plan.route.mode);
  const xp = useCountUp(reward ? run.xp : 0, 1200, 1100);
  const [lines, setLines] = useState(false);
  const before = reward ? levelOf(reward.before.xp) : null;
  const after = reward ? levelOf(reward.after.xp) : null;
  const [barW, setBarW] = useState(() => (!before || reward?.levelUp ? 0 : (before.into / before.need) * 100));

  useEffect(() => {
    if (!reward) return;
    const ts: ReturnType<typeof setTimeout>[] = [];
    for (let i = 0; i < run.stars; i++) ts.push(setTimeout(() => sfx.star(i), 250 + i * 280));
    if (run.stars === 0) ts.push(setTimeout(sfx.fail, 300));
    ts.push(setTimeout(sfx.coin, 1100));
    ts.push(setTimeout(() => after && setBarW((after.into / after.need) * 100), 1200));
    return () => ts.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reward]);

  const fail = run.stars === 0;
  return (
    <section className="relative animate-pop overflow-hidden rounded-3xl bg-gradient-to-b from-ink-700/90 via-ink-800 to-ink-850 p-5 ring-1 ring-white/10" aria-label="Trip summary">
      <svg width="0" height="0" className="absolute" aria-hidden>
        <defs>
          <linearGradient id="qc-gold" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fef3c7" />
            <stop offset="0.45" stopColor="#fbbf24" />
            <stop offset="1" stopColor="#f97316" />
          </linearGradient>
        </defs>
      </svg>
      {/* sunburst behind the stars */}
      {!fail && (
        <div aria-hidden className="pointer-events-none absolute left-1/2 top-[-130px] -ml-[200px] h-[400px] w-[400px]">
          <div
            className="h-full w-full animate-spin-slow opacity-60"
            style={{
              background: "repeating-conic-gradient(from 0deg, rgba(251,191,36,0.16) 0deg 9deg, transparent 9deg 22deg)",
              maskImage: "radial-gradient(circle, black 15%, transparent 62%)",
              WebkitMaskImage: "radial-gradient(circle, black 15%, transparent 62%)",
            }}
          />
        </div>
      )}

      <h2 className={`relative text-center font-logo text-[27px] leading-tight ${fail ? "text-rose-400" : "text-gold"}`}>{run.title}</h2>
      <div className="relative mt-2 flex items-end justify-center gap-1">
        {[0, 1, 2].map((i) => (
          <Star key={i} i={i} on={i < run.stars} />
        ))}
      </div>
      <p className="relative mt-1 text-center text-xs text-slate-400">{run.subtitle}</p>

      <div className="relative mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-2xl bg-black/30 p-3 ring-1 ring-white/10">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Arrive</p>
          <p className="font-display text-[32px] font-bold leading-none text-white">{fmtTime(plan.arrival_eta)}</p>
          <p className="mt-1 text-[11px] text-slate-400">
            leave {fmtTime(plan.departure_time)} · {mode?.icon} {mode?.label}
          </p>
        </div>
        <div className="rounded-2xl bg-black/30 p-3 ring-1 ring-white/10">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Time cost</p>
          <p className="font-display text-[32px] font-bold leading-none text-brand-300">{fmtAdded(plan.total_added_min)}</p>
          <p className="mt-1 text-[11px] text-slate-400">added by your stops</p>
        </div>
      </div>
      <div className="relative mt-2 grid grid-cols-3 gap-2 text-center">
        {[
          { v: `${run.found}/${run.requested}`, l: "quests found" },
          { v: fmtDuration(plan.route.duration_s), l: "base trip" },
          { v: fmtDistance(plan.route.distance_m), l: "distance" },
        ].map((x) => (
          <div key={x.l} className="rounded-xl bg-white/5 px-2 py-2 ring-1 ring-white/5">
            <p className="font-display text-sm font-bold text-white">{x.v}</p>
            <p className="text-[10px] uppercase tracking-wide text-slate-400">{x.l}</p>
          </div>
        ))}
      </div>

      {reward && after && (
        <div className="relative mt-3 rounded-2xl bg-amber-400/10 p-3 ring-1 ring-amber-300/25">
          <div className="flex items-center justify-between">
            <span className="font-logo text-2xl text-gold">+{xp} XP</span>
            <button
              type="button"
              className="text-[11px] font-semibold text-amber-200/80 hover:text-amber-100"
              onClick={() => setLines((s) => !s)}
              aria-expanded={lines}
            >
              {lines ? "hide" : "how it's earned"} <span className={`inline-block transition ${lines ? "rotate-180" : ""}`}>▾</span>
            </button>
          </div>
          {lines && (
            <ul className="mt-2 animate-slide-down space-y-1 text-xs">
              {run.lines.map((l) => (
                <li key={l.label} className="flex justify-between text-slate-300">
                  <span>{l.label}</span>
                  <span className="font-mono text-amber-200">+{l.xp}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-2 flex items-center gap-2 text-[11px]">
            <span className="font-display font-semibold text-amber-200">LV {after.level}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-black/50">
              <div className="xp-fill h-full rounded-full transition-[width] duration-1000 ease-out" style={{ width: `${Math.max(3, barW)}%` }} />
            </div>
            <span className="font-mono text-slate-400">
              {after.into}/{after.need}
            </span>
          </div>
          {reward.levelUp && (
            <p className="mt-2 animate-pop text-center font-logo text-sm text-amber-300" style={{ animationDelay: "1.4s" }}>
              ▲ Level up — level {after.level}
              {before && before.rank !== after.rank ? `, ${after.rank}` : ""}!
            </p>
          )}
          {reward.newBadges.length > 0 && (
            <div className="mt-2.5 flex flex-wrap justify-center gap-1.5">
              {reward.newBadges.map((b, i) => (
                <span
                  key={b.id}
                  className="badge animate-pop bg-amber-300/15 text-amber-200 ring-1 ring-amber-300/30"
                  style={{ animationDelay: `${1.6 + i * 0.15}s` }}
                  title={b.desc}
                >
                  {b.icon} {b.name}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
