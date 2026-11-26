import { useCallback, useRef, useState } from "react";
import type { Mode, TripPlan } from "../types";
import { applyRun, EMPTY_STATS, type GameStats, type Reward } from "./game";
import { setSfxEnabled } from "./sfx";

// per-browser progress; it's a convenience, so storage failures just mean a fresh start
const KEY = "sidequest.game.v1";
const SOUND_KEY = "sidequest.sound";

function load(): GameStats {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return EMPTY_STATS;
    const s = JSON.parse(raw) as Partial<GameStats>;
    return { ...EMPTY_STATS, ...s, badges: { ...(s.badges ?? {}) } };
  } catch {
    return EMPTY_STATS;
  }
}

function save(s: GameStats) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* private mode / blocked storage */
  }
}

function loadSound(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) === "1";
  } catch {
    return false;
  }
}

export function useGame() {
  const [stats, setStats] = useState<GameStats>(load);
  const ref = useRef(stats);
  const [sound, setSoundState] = useState(() => {
    const on = loadSound();
    setSfxEnabled(on);
    return on;
  });

  const award = useCallback((plan: TripPlan, mode: Mode): Reward => {
    const r = applyRun(ref.current, plan, mode);
    ref.current = r.after;
    setStats(r.after);
    save(r.after);
    return r;
  }, []);

  const setSound = useCallback((on: boolean) => {
    setSfxEnabled(on);
    setSoundState(on);
    try {
      localStorage.setItem(SOUND_KEY, on ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, []);

  const reset = useCallback(() => {
    ref.current = EMPTY_STATS;
    setStats(EMPTY_STATS);
    save(EMPTY_STATS);
  }, []);

  return { stats, award, sound, setSound, reset };
}
