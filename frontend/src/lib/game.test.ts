import { describe, expect, it } from "vitest";
import type { PlaceCandidate, StopPlan, TripPlan } from "../types";
import { applyRun, EMPTY_STATS, levelOf, scoreRun, xpToNext } from "./game";

function cand(id: string, over: Partial<PlaceCandidate> = {}): PlaceCandidate {
  return {
    osm_id: id,
    name: id,
    lat: 1.35,
    lng: 103.8,
    tags: {},
    open_at_eta: true,
    detour_min: 3,
    detour_exact: true,
    eta: "2026-11-26T16:24:00+08:00",
    score: 3,
    score_breakdown: { detour: 3 },
    matched_stop_ids: [],
    evidence: [],
    offset_m: 200,
    along_s: 600,
    kind: "standalone",
    ...over,
  };
}

function stop(id: string, category: string, chosen: PlaceCandidate | null, over: Partial<StopPlan> = {}, prayer = false): StopPlan {
  return {
    request: {
      id,
      query: category,
      category,
      time_window: prayer ? { type: "prayer", value: "asr", relation: "at" } : { type: "any" },
      constraints: { open_at_eta: true, dietary: [] },
    },
    eta_window: { start: "2026-11-26T16:00:00+08:00", end: "2026-11-26T17:00:00+08:00" },
    candidates: chosen ? [chosen] : [],
    chosen,
    added_min: chosen ? chosen.detour_min : 0,
    warnings: [],
    ...over,
  };
}

function plan(stops: StopPlan[], total: number, over: Partial<TripPlan> = {}): TripPlan {
  return {
    route: { geometry: [], duration_s: 2400, distance_m: 30_000, mode: "drive", provider: "onemap", legs: [] },
    departure_time: "2026-11-26T15:55:00+08:00",
    stops,
    prayer_times: [],
    timeline: [],
    total_added_min: total,
    arrival_eta: "2026-11-26T17:05:00+08:00",
    gmaps_url: "",
    gmaps_leg_urls: [],
    warnings: [],
    ...over,
  };
}

describe("scoreRun", () => {
  it("gives 3 stars when every quest is found cheaply", () => {
    const p = plan([stop("s1", "mosque", cand("m"), {}, true), stop("s2", "ice_cream", cand("i", { detour_min: 5 }))], 8);
    const r = scoreRun(p);
    expect(r.stars).toBe(3);
    expect(r.lines.map((l) => l.label)).toContain("Prayer on time ×1");
    // 50 route + 50 found + 20 prayer + 22 efficiency + 30 stars
    expect(r.xp).toBe(172);
  });

  it("gives 2 stars when all found but detours are long", () => {
    expect(scoreRun(plan([stop("s1", "cafe", cand("c", { detour_min: 14 }))], 14)).stars).toBe(2);
  });

  it("gives 1 star for a partial clear and 0 when nothing is found", () => {
    expect(scoreRun(plan([stop("s1", "cafe", cand("c")), stop("s2", "atm", null)], 3)).stars).toBe(1);
    const fail = scoreRun(plan([stop("s1", "atm", null)], 0));
    expect(fail.stars).toBe(0);
    expect(fail.title).toBe("Quest failed");
  });

  it("counts a combined stop once for the 3-star budget", () => {
    const shared = cand("mall", { detour_min: 6 });
    const p = plan([stop("s1", "cafe", shared), stop("s2", "atm", shared, { covered_by: "s1" })], 6);
    const r = scoreRun(p);
    expect(r.stars).toBe(2); // 6 min > 5 min for one physical stop
    expect(r.lines.some((l) => l.label.startsWith("Combo"))).toBe(true);
  });
});

describe("levels", () => {
  it("levels up on the threshold", () => {
    expect(levelOf(0).level).toBe(1);
    expect(levelOf(xpToNext(1) - 1).level).toBe(1);
    expect(levelOf(xpToNext(1)).level).toBe(2);
    expect(levelOf(xpToNext(1) + xpToNext(2)).rank).toBe("Explorer");
  });
});

describe("applyRun", () => {
  it("unlocks badges once and accumulates stats", () => {
    const p = plan([stop("s1", "mosque", cand("m"), {}, true), stop("s2", "ice_cream", cand("i", { detour_min: 0.5 }))], 3.5);
    const first = applyRun(EMPTY_STATS, p, "drive", new Date("2026-11-26T08:00:00Z"));
    const ids = first.newBadges.map((b) => b.id);
    expect(ids).toEqual(expect.arrayContaining(["first", "prayer", "sweet", "foodie", "bullseye", "perfect", "longhaul"]));
    expect(ids).not.toContain("rail");
    expect(first.after.trips).toBe(1);
    expect(first.after.cleared).toBe(2);

    const again = applyRun(first.after, p, "transit");
    expect(again.newBadges.map((b) => b.id)).toEqual(["rail"]);
    expect(again.after.xp).toBe(first.after.xp + again.run.xp);
  });
});
