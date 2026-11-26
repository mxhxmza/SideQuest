import { describe, expect, it } from "vitest";
import { gmapsUrl, legUrls } from "./deeplink";
import { addedMin, fmtAdded, fmtDistance, fmtDuration, fmtTime, fmtWindow, inputToIso, localInputNow } from "./format";

describe("deeplink", () => {
  const a = { lat: 1.3483, lng: 103.6831 };
  const b = { lat: 1.3644, lng: 103.9915 };
  it("builds a driving link with waypoints", () => {
    const u = gmapsUrl(a, b, [{ lat: 1.35, lng: 103.8 }], "drive");
    expect(u).toBe(
      "https://www.google.com/maps/dir/?api=1&origin=1.348300,103.683100&destination=1.364400,103.991500" +
        "&travelmode=driving&waypoints=1.350000,103.800000",
    );
  });
  it("drops waypoints for transit and caps at 9", () => {
    expect(gmapsUrl(a, b, [a], "transit")).not.toContain("waypoints");
    const many = Array.from({ length: 12 }, (_, i) => ({ lat: 1.3 + i / 100, lng: 103.8 }));
    expect(gmapsUrl(a, b, many, "walk").split("|").length).toBe(9);
  });
  it("makes one link per leg", () => {
    const legs = legUrls([{ label: "A", at: a }, { label: "S", at: a }, { label: "B", at: b }], "transit");
    expect(legs.map((l) => l.label)).toEqual(["A → S", "S → B"]);
    expect(legs[1].url).toContain("travelmode=transit");
  });
});

describe("format", () => {
  it("formats times in Singapore", () => {
    expect(fmtTime("2026-11-27T05:05:00Z")).toBe("13:05");
  });
  it("formats added minutes and durations", () => {
    expect(fmtAdded(5.6)).toBe("+6 min");
    expect(fmtAdded(-1)).toBe("+0 min");
    expect(fmtAdded(65)).toBe("+1 h 05 min");
    expect(fmtDuration(2520)).toBe("42 min");
    expect(fmtDuration(5400)).toBe("1 h 30 min");
    expect(fmtDistance(850)).toBe("850 m");
    expect(fmtDistance(45210)).toBe("45 km");
  });
  it("round-trips the departure input", () => {
    expect(localInputNow(new Date("2026-11-27T04:31:10Z"))).toBe("2026-11-27T12:35");
    expect(inputToIso("2026-11-27T12:35")).toBe("2026-11-27T12:35:00+08:00");
  });
  it("describes windows", () => {
    expect(fmtWindow({ type: "clock_time", value: "13:00" })).toBe("~13:00");
    expect(fmtWindow({ type: "prayer", value: "asr" })).toBe("@Asar");
    expect(fmtWindow({ type: "prayer", value: "asr", until: "18:00" })).toBe("@Asar–18:00");
    expect(addedMin({ detour_min: 4.5, wait_min: 3 })).toBe(7.5);
    expect(addedMin({ detour_min: 4.5 })).toBe(4.5);
    expect(fmtWindow({ type: "prayer", value: "maghrib", relation: "before" })).toBe("before Maghrib");
    expect(fmtWindow({ type: "minutes_in", value: 45 })).toBe("45 min in");
    expect(fmtWindow({ type: "any" })).toBe("any time");
  });
});
