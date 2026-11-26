import { useState } from "react";
import type { Category, Cuisine, StopRequest, TimeWindow } from "../types";
import { fmtWindow, PRAYER_LABEL } from "../lib/format";

interface Props {
  stops: StopRequest[];
  categories: Category[];
  cuisines: Cuisine[];
  onChange: (stops: StopRequest[]) => void;
}

const DIETS = ["halal", "vegetarian", "vegan"];
const DIET_KINDS = ["meal", "search"];
const CUISINE_KINDS = ["meal"];

export default function StopChips({ stops, categories, cuisines, onChange }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const catOf = (k: string) => categories.find((c) => c.key === k);
  const cuisineLabel = (k: string) => cuisines.find((c) => c.key === k)?.label ?? k.replace(/_/g, " ");

  const update = (id: string, patch: Partial<StopRequest>) =>
    onChange(stops.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  const updateWin = (s: StopRequest, patch: Partial<TimeWindow>) =>
    update(s.id, { time_window: { ...s.time_window, ...patch } });

  const add = () => {
    const n = Math.max(0, ...stops.map((s) => Number(s.id.replace(/\D/g, "")) || 0)) + 1;
    const s: StopRequest = {
      id: `s${n}`,
      query: "",
      category: "meal",
      time_window: { type: "any" },
      constraints: { open_at_eta: true, dietary: [] },
    };
    onChange([...stops, s]);
    setEditing(s.id);
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {stops.map((s, i) => {
          const c = catOf(s.category);
          const label = s.category === "keyword" ? (s.label ?? s.name_keywords?.[0] ?? "Search") : (c?.label ?? s.label ?? s.category);
          return (
            <button
              key={s.id + s.category + s.query}
              type="button"
              onClick={() => setEditing(editing === s.id ? null : s.id)}
              className={`chip animate-pop ${editing === s.id ? "border-brand-300 bg-brand-400/15 ring-4 ring-brand-400/20" : ""}`}
              style={{ animationDelay: `${i * 70}ms` }}
              title={s.query || undefined}
            >
              <span className="hex flex h-5 w-6 items-center justify-center bg-gradient-to-br from-brand-300 to-brand-600 font-display text-[10px] font-bold text-ink-950">
                {i + 1}
              </span>
              <span aria-hidden>{c?.icon ?? s.icon}</span>
              {s.constraints.dietary.length > 0 && (
                <span className="font-semibold capitalize text-emerald-300">{s.constraints.dietary.join("/")}</span>
              )}
              {(s.constraints.cuisine ?? []).length > 0 && (
                <span className="font-semibold capitalize text-orange-300">{s.constraints.cuisine!.map(cuisineLabel).join("/")}</span>
              )}
              <span className="font-medium text-white">{label}</span>
              <span className="text-slate-400">· {fmtWindow(s.time_window)}</span>
            </button>
          );
        })}
        <button type="button" onClick={add} className="chip border-dashed text-slate-400">
          + Add
        </button>
      </div>

      {stops
        .filter((s) => s.id === editing)
        .map((s) => {
          const c = catOf(s.category);
          const allowsDiet = DIET_KINDS.includes(c?.kind ?? "");
          return (
            <div key={s.id} className="mt-3 animate-slide-down space-y-3 rounded-2xl border border-white/10 bg-ink-900/80 p-3 text-sm shadow-xl shadow-black/30">
              <div className="grid grid-cols-2 gap-2">
                <label className="col-span-2 sm:col-span-1">
                  <span className="lbl">What</span>
                  <select
                    className="input"
                    value={s.category}
                    onChange={(e) => {
                      const nc = catOf(e.target.value);
                      update(s.id, {
                        category: e.target.value,
                        dwell_min: nc?.dwell_min ?? s.dwell_min,
                        label: nc?.key === "keyword" ? s.label : nc?.label,
                        icon: nc?.icon,
                        constraints: {
                          ...s.constraints,
                          dietary: DIET_KINDS.includes(nc?.kind ?? "") ? s.constraints.dietary : [],
                          cuisine: CUISINE_KINDS.includes(nc?.kind ?? "") ? s.constraints.cuisine : [],
                        },
                      });
                    }}
                  >
                    {categories.map((k) => (
                      <option key={k.key} value={k.key}>
                        {k.icon} {k.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="col-span-2 sm:col-span-1">
                  <span className="lbl">Stay (min)</span>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    max={240}
                    value={s.dwell_min ?? c?.dwell_min ?? 15}
                    onChange={(e) => update(s.id, { dwell_min: Number(e.target.value) })}
                  />
                </label>
              </div>

              {s.category === "keyword" && (
                <label className="block">
                  <span className="lbl">Place name contains</span>
                  <input
                    className="input"
                    value={(s.name_keywords ?? [])[0] ?? ""}
                    placeholder="e.g. durian"
                    onChange={(e) => update(s.id, { name_keywords: [e.target.value], label: e.target.value })}
                  />
                </label>
              )}

              {CUISINE_KINDS.includes(c?.kind ?? "") && cuisines.length > 0 && (
                <label className="block">
                  <span className="lbl">Cuisine</span>
                  <select
                    className="input"
                    value={(s.constraints.cuisine ?? [])[0] ?? ""}
                    onChange={(e) => update(s.id, { constraints: { ...s.constraints, cuisine: e.target.value ? [e.target.value] : [] } })}
                  >
                    <option value="">Any cuisine</option>
                    {cuisines.map((k) => (
                      <option key={k.key} value={k.key}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div className="grid grid-cols-2 gap-2">
                <label>
                  <span className="lbl">When</span>
                  <select
                    className="input"
                    value={s.time_window.type}
                    onChange={(e) => {
                      const type = e.target.value as TimeWindow["type"];
                      const value = type === "clock_time" ? "13:00" : type === "minutes_in" ? 45 : type === "prayer" ? "asr" : null;
                      updateWin(s, { type, value, tolerance_min: null, until: null });
                    }}
                  >
                    <option value="any">Anywhere on the way</option>
                    <option value="clock_time">Around a time</option>
                    <option value="minutes_in">Minutes into the trip</option>
                    <option value="prayer">At a prayer time</option>
                  </select>
                </label>
                <label>
                  <span className="lbl">&nbsp;</span>
                  {s.time_window.type === "clock_time" && (
                    <input
                      className="input"
                      type="time"
                      value={String(s.time_window.value ?? "13:00")}
                      onChange={(e) => updateWin(s, { value: e.target.value })}
                    />
                  )}
                  {s.time_window.type === "minutes_in" && (
                    <input
                      className="input"
                      type="number"
                      min={0}
                      step={5}
                      value={Number(s.time_window.value ?? 45)}
                      onChange={(e) => updateWin(s, { value: Number(e.target.value) })}
                    />
                  )}
                  {s.time_window.type === "prayer" && (
                    <div className="flex gap-1">
                      <select
                        className="input w-24"
                        value={s.time_window.relation ?? "at"}
                        onChange={(e) => {
                          const relation = e.target.value as TimeWindow["relation"];
                          updateWin(s, relation === "before" ? { relation, until: null } : { relation });
                        }}
                      >
                        <option value="at">at</option>
                        <option value="before">before</option>
                      </select>
                      <select
                        className="input flex-1"
                        value={String(s.time_window.value ?? "asr")}
                        onChange={(e) => updateWin(s, { value: e.target.value })}
                      >
                        {Object.entries(PRAYER_LABEL).map(([k, v]) => (
                          <option key={k} value={k}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </label>
              </div>

              {s.time_window.type === "prayer" && s.time_window.relation !== "before" && (
                <label className="block">
                  <span className="lbl">Until (optional)</span>
                  <input
                    className="input"
                    type="time"
                    value={s.time_window.until ?? ""}
                    onChange={(e) => updateWin(s, { until: e.target.value || null })}
                  />
                </label>
              )}

              {allowsDiet && (
                <div className="flex flex-wrap gap-2">
                  {DIETS.map((d) => {
                    const on = s.constraints.dietary.includes(d);
                    return (
                      <button
                        key={d}
                        type="button"
                        onClick={() =>
                          update(s.id, {
                            constraints: {
                              ...s.constraints,
                              dietary: on ? s.constraints.dietary.filter((x) => x !== d) : [...s.constraints.dietary, d],
                            },
                          })
                        }
                        className={`rounded-full px-3 py-1 text-xs font-semibold capitalize transition ${
                          on ? "bg-emerald-500 text-ink-950 shadow-[0_0_12px_rgba(16,185,129,0.5)]" : "bg-white/5 text-slate-300 ring-1 ring-white/10 hover:bg-emerald-500/15"
                        }`}
                      >
                        {on ? "✓ " : ""}
                        {d}
                      </button>
                    );
                  })}
                </div>
              )}
              <label className="flex items-center gap-2 text-slate-300">
                <input
                  type="checkbox"
                  className="accent-brand-400"
                  checked={s.constraints.open_at_eta}
                  onChange={(e) => update(s.id, { constraints: { ...s.constraints, open_at_eta: e.target.checked } })}
                />
                Prefer places open when I arrive
              </label>
              <div className="flex justify-between">
                <button
                  type="button"
                  className="text-xs font-semibold text-rose-400 hover:underline"
                  onClick={() => {
                    onChange(stops.filter((x) => x.id !== s.id));
                    setEditing(null);
                  }}
                >
                  Remove stop
                </button>
                <button type="button" className="btn-ghost px-4 py-1.5 font-semibold" onClick={() => setEditing(null)}>
                  Done
                </button>
              </div>
            </div>
          );
        })}
    </div>
  );
}
