/** The game layer: stars, XP, levels and badges computed from a TripPlan.
 * Pure functions here; persistence lives in useGame.ts. */
import type { Mode, TripPlan } from "../types";
import { addedMin, TZ } from "./format";

export interface GameStats {
  xp: number;
  trips: number;
  /** side quests found, all time */
  cleared: number;
  /** 3-star trips */
  perfect: number;
  /** badge id → ISO date unlocked */
  badges: Record<string, string>;
}

export const EMPTY_STATS: GameStats = { xp: 0, trips: 0, cleared: 0, perfect: 0, badges: {} };

export interface XpLine {
  label: string;
  xp: number;
}

export interface RunResult {
  stars: 0 | 1 | 2 | 3;
  title: string;
  subtitle: string;
  lines: XpLine[];
  xp: number;
  found: number;
  requested: number;
}

const FOOD = new Set(["meal", "hawker", "cafe", "ice_cream", "bakery"]);
const PRAYER = new Set(["mosque", "prayer_room"]);

/** Distinct places actually visited (a combined stop counts once). */
function physicalStops(plan: TripPlan): number {
  return new Set(plan.stops.filter((s) => s.chosen && !s.covered_by).map((s) => s.chosen!.osm_id)).size;
}

/** Budget for 3 stars: ≤ 5 extra minutes per place visited. */
export const PERFECT_MIN_PER_STOP = 5;

export function scoreRun(plan: TripPlan): RunResult {
  const requested = plan.stops.length;
  const found = plan.stops.filter((s) => s.chosen).length;
  const combos = plan.stops.filter((s) => s.chosen && s.covered_by).length;
  const prayers = plan.stops.filter((s) => s.chosen && s.request.time_window.type === "prayer").length;
  const added = plan.total_added_min;

  let stars: RunResult["stars"];
  let title: string;
  let subtitle: string;
  if (requested === 0) {
    stars = 1;
    title = "Route ready";
    subtitle = "Add side quests to earn more stars";
  } else if (found === 0) {
    stars = 0;
    title = "Quest failed";
    subtitle = "Nothing suitable along this route";
  } else if (found < requested) {
    stars = 1;
    title = "Partial clear";
    subtitle = `${requested - found} side quest${requested - found > 1 ? "s" : ""} not found`;
  } else if (added <= PERFECT_MIN_PER_STOP * Math.max(1, physicalStops(plan))) {
    stars = 3;
    title = "Perfect run!";
    subtitle = "Every side quest, barely any detour";
  } else {
    stars = 2;
    title = "Quest complete!";
    subtitle = "Every side quest found";
  }

  const lines: XpLine[] = [{ label: "Route planned", xp: 50 }];
  if (found) lines.push({ label: `Side quests found ×${found}`, xp: 25 * found });
  if (combos) lines.push({ label: `Combo stops ×${combos}`, xp: 20 * combos });
  if (prayers) lines.push({ label: `Prayer on time ×${prayers}`, xp: 20 * prayers });
  const efficiency = found ? Math.max(0, Math.round(30 - added)) : 0;
  if (efficiency) lines.push({ label: "Efficiency bonus", xp: efficiency });
  if (stars) lines.push({ label: `Star bonus ×${stars}`, xp: 10 * stars });
  return { stars, title, subtitle, lines, xp: lines.reduce((n, l) => n + l.xp, 0), found, requested };
}

// ---------------------------------------------------------------- levels

const RANKS: [number, string][] = [
  [1, "Wanderer"],
  [3, "Explorer"],
  [5, "Navigator"],
  [8, "Pathfinder"],
  [12, "Route Master"],
  [20, "Legend of the Lion City"],
];

/** XP needed to go from level n to n+1. */
export const xpToNext = (level: number) => 100 + (level - 1) * 50;

export function levelOf(xp: number): { level: number; into: number; need: number; rank: string } {
  let level = 1;
  let left = Math.max(0, xp);
  while (left >= xpToNext(level)) {
    left -= xpToNext(level);
    level++;
  }
  const rank = RANKS.filter(([l]) => level >= l).pop()![1];
  return { level, into: left, need: xpToNext(level), rank };
}

// ---------------------------------------------------------------- badges

export interface Ctx {
  mode: Mode;
  stats: GameStats; // after this trip is counted
  stars: number;
}

export interface Badge {
  id: string;
  icon: string;
  name: string;
  desc: string;
  test: (plan: TripPlan, ctx: Ctx) => boolean;
}

const hourSG = (iso: string) => {
  const parts = new Intl.DateTimeFormat("en-SG", { hour: "numeric", minute: "numeric", hour12: false, timeZone: TZ }).formatToParts(new Date(iso));
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0) % 24;
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return h + m / 60;
};

const chosen = (plan: TripPlan) => plan.stops.filter((s) => s.chosen);

export const BADGES: Badge[] = [
  { id: "first", icon: "🗺️", name: "First Steps", desc: "Plan your first trip", test: () => true },
  {
    id: "prayer",
    icon: "🕌",
    name: "Prayer Keeper",
    desc: "Fit a mosque or surau into a prayer time",
    test: (p) => chosen(p).some((s) => PRAYER.has(s.request.category) && s.request.time_window.type === "prayer"),
  },
  { id: "combo", icon: "⚡", name: "Combo!", desc: "Clear two side quests at one stop", test: (p) => chosen(p).some((s) => s.covered_by) },
  {
    id: "bullseye",
    icon: "🎯",
    name: "Bullseye",
    desc: "Find a stop that adds under a minute",
    test: (p) => chosen(p).some((s) => !s.covered_by && addedMin(s.chosen!) < 1),
  },
  {
    id: "hattrick",
    icon: "🔱",
    name: "Hat Trick",
    desc: "Clear 3+ side quests in one trip",
    test: (p) => p.stops.length >= 3 && chosen(p).length === p.stops.length,
  },
  { id: "foodie", icon: "🍜", name: "Foodie", desc: "Find a meal, hawker, café or bakery stop", test: (p) => chosen(p).some((s) => FOOD.has(s.request.category)) },
  { id: "sweet", icon: "🍨", name: "Sweet Tooth", desc: "Find ice cream or dessert", test: (p) => chosen(p).some((s) => s.request.category === "ice_cream") },
  {
    id: "halal",
    icon: "🥘",
    name: "Halal Hunter",
    desc: "Find a stop tagged halal in OpenStreetMap",
    test: (p) =>
      chosen(p).some(
        (s) => s.request.constraints.dietary.includes("halal") && s.chosen!.evidence.some((e) => e.strength === "strong" && /halal/i.test(e.text)),
      ),
  },
  { id: "treasure", icon: "🔎", name: "Treasure Hunter", desc: "Find a place by name search", test: (p) => chosen(p).some((s) => s.request.category === "keyword") },
  { id: "rail", icon: "🚇", name: "Rail Rider", desc: "Plan a public-transport trip", test: (_, c) => c.mode === "transit" },
  { id: "green", icon: "🌿", name: "Green Machine", desc: "Plan a walking or cycling trip", test: (_, c) => c.mode === "walk" || c.mode === "cycle" },
  { id: "longhaul", icon: "🛣️", name: "Long Haul", desc: "Plan a trip longer than 25 km", test: (p) => p.route.distance_m >= 25_000 },
  {
    id: "owl",
    icon: "🦉",
    name: "Night Owl",
    desc: "Leave between 10 pm and 5 am",
    test: (p) => {
      const h = hourSG(p.departure_time);
      return h >= 22 || h < 5;
    },
  },
  {
    id: "bird",
    icon: "🐦",
    name: "Early Bird",
    desc: "Leave between 5 and 7:30 am",
    test: (p) => {
      const h = hourSG(p.departure_time);
      return h >= 5 && h < 7.5;
    },
  },
  { id: "perfect", icon: "⭐", name: "Perfectionist", desc: "Earn 3 stars on a trip", test: (_, c) => c.stars === 3 },
  { id: "veteran", icon: "🏅", name: "Veteran", desc: "Plan 10 trips", test: (_, c) => c.stats.trips >= 10 },
];

export interface Reward {
  run: RunResult;
  before: GameStats;
  after: GameStats;
  newBadges: Badge[];
  levelUp: boolean;
}

/** Apply one planned trip to the player's stats. */
export function applyRun(stats: GameStats, plan: TripPlan, mode: Mode, now = new Date()): Reward {
  const run = scoreRun(plan);
  const counted: GameStats = {
    xp: stats.xp + run.xp,
    trips: stats.trips + 1,
    cleared: stats.cleared + run.found,
    perfect: stats.perfect + (run.stars === 3 ? 1 : 0),
    badges: { ...stats.badges },
  };
  const ctx: Ctx = { mode, stats: counted, stars: run.stars };
  const newBadges = BADGES.filter((b) => !stats.badges[b.id] && b.test(plan, ctx));
  for (const b of newBadges) counted.badges[b.id] = now.toISOString();
  return { run, before: stats, after: counted, newBadges, levelUp: levelOf(counted.xp).level > levelOf(stats.xp).level };
}
