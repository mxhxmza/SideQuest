import { useEffect, useState } from "react";

const TIERS = [
  {
    icon: "📱",
    title: "Your device",
    sub: "React PWA",
    items: ["React 18 + TypeScript (Vite)", "MapLibre GL + OpenFreeMap tiles", "Live prompt parsing as you type", "Stars, XP & badges — stored locally"],
    grad: "from-brand-300 to-cyan-500",
  },
  {
    icon: "⚙️",
    title: "Planner API",
    sub: "Python · FastAPI",
    items: ["POST /api/parse — sentence → stops", "POST /api/plan — the whole trip", "GET /api/geocode — place search", "GET /api/prayer-times — MUIS times"],
    grad: "from-violet-300 to-fuchsia-500",
  },
  {
    icon: "🌐",
    title: "Data & providers",
    sub: "Free tiers, with fallbacks",
    items: ["OneMap (SLA) routing + search", "OSRM / OpenRouteService fallback", "44k OpenStreetMap places, local", "MUIS prayer times (adhanpy), offline"],
    grad: "from-amber-200 to-orange-500",
  },
];

const STAGES = [
  {
    icon: "🗣️",
    name: "Parse",
    detail:
      "A rules parser (optionally a local or hosted LLM, always falling back to rules) turns your sentence into typed stops: one of 28 place types, a cuisine, dietary needs, a time window (“~1pm”, “before 10am”, “45 min in”, “at Asar”) and how long you'll stay. Anything it can't place becomes a name search instead of being dropped.",
    file: "providers/llm/rules.py",
  },
  {
    icon: "🛣️",
    name: "Route",
    detail: "The base A→B route comes from OneMap. If it fails or is rate-limited, the chain falls back to OpenRouteService, then OSRM servers. Responses are cached in SQLite.",
    file: "providers/routing/chain.py",
  },
  {
    icon: "⏲️",
    name: "Timeline",
    detail: "Every vertex of the route gets a cumulative time, so the planner can answer “where will I be at 16:16?” and “when do I pass this point?” in microseconds.",
    file: "core/timeline.py",
  },
  {
    icon: "🎯",
    name: "Windows",
    detail:
      "Each stop's time window is mapped onto a stretch of the route — ±tolerance around 1pm, “before 10am”, a minutes-into-trip mark, or a prayer time. Earlier stops delay later ones, so windows are re-computed as stops are placed.",
    file: "core/segments.py",
  },
  {
    icon: "📍",
    name: "Search",
    detail:
      "Candidates come from an SQLite R*Tree of OpenStreetMap places, within a corridor around that stretch. Tag filters pick the category (a church is amenity=place_of_worship + religion=christian); opening hours are evaluated at your ETA; cuisine and dietary tags are checked as evidence.",
    file: "providers/places/osm_sqlite.py",
  },
  {
    icon: "📐",
    name: "Estimate",
    detail: "A cheap detour estimate for every candidate: 2 × distance off-route × 1.3 ÷ travel speed. Good enough to shortlist, never shown as exact.",
    file: "core/detour.py",
  },
  {
    icon: "🔬",
    name: "Verify",
    detail: "The best few are re-routed for real (one matrix call per stop, or pairwise legs) until the winner's minutes are exact, not estimated.",
    file: "core/planner.py",
  },
  {
    icon: "⚖️",
    name: "Score",
    detail:
      "Score = minutes added + penalties in minutes (closed at ETA, unknown hours, outside the window, weak evidence, pushing later stops late) − a combo bonus. Lowest wins, and every term is shown in “Why this rank?”.",
    file: "core/scoring.py",
  },
  {
    icon: "🧩",
    name: "Combine",
    detail:
      "Stops are placed in order, greedily. Two quests that fit in the same place — or the same mall — merge into one stop that costs zero extra minutes. You can pin any alternative and the rest re-plans.",
    file: "core/planner.py",
  },
  {
    icon: "🚀",
    name: "Hand-off",
    detail: "The final timeline (with Muslim prayer times when you asked for a mosque) and a Google Maps link with your stops as waypoints (one link per leg for public transport, since Maps can't add transit waypoints).",
    file: "core/deeplink.py",
  },
];

const CHAINS = [
  { label: "Routing", icon: "🛣️", items: ["OneMap", "OpenRouteService", "OSRM (FOSSGIS)", "OSRM demo"] },
  { label: "Place search", icon: "🔍", items: ["OneMap", "Photon", "Local POI names"] },
  { label: "Parsing", icon: "🗣️", items: ["LLM, if configured (Ollama / OpenAI-compatible)", "Rules parser (default)"] },
];

function Connector() {
  return (
    <div aria-hidden className="flex items-center justify-center lg:px-1">
      <span className="flow-y h-8 w-[2px] rounded lg:hidden" />
      <span className="flow-x hidden h-[2px] w-10 rounded lg:block" />
      <span className="hidden text-brand-300 lg:block">▶</span>
      <span className="text-brand-300 lg:hidden">▼</span>
    </div>
  );
}

export default function Architecture() {
  const [stage, setStage] = useState(0);
  const [auto, setAuto] = useState(true);

  // demo mode: step through the pipeline until the visitor picks a stage
  useEffect(() => {
    if (!auto || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setStage((s) => (s + 1) % STAGES.length), 4200);
    return () => clearInterval(t);
  }, [auto]);
  const cur = STAGES[stage];

  return (
    <div className="space-y-14">
      {/* three tiers */}
      <div className="reveal grid grid-cols-1 items-stretch gap-0 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
        {TIERS.map((t, i) => (
          <div key={t.title} className="contents">
            <div className="card relative overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:border-white/20">
              <div aria-hidden className={`absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-to-br opacity-20 blur-2xl ${t.grad}`} />
              <div className="mb-3 flex items-center gap-3">
                <span className={`hex flex h-11 w-12 items-center justify-center bg-gradient-to-br text-xl ${t.grad}`}>{t.icon}</span>
                <div>
                  <p className="font-display text-lg font-semibold text-white">{t.title}</p>
                  <p className="text-xs text-slate-400">{t.sub}</p>
                </div>
              </div>
              <ul className="space-y-1.5 text-sm text-slate-300">
                {t.items.map((x) => (
                  <li key={x} className="flex gap-2">
                    <span className="text-brand-300">›</span>
                    <span className="font-mono text-[12.5px]">{x}</span>
                  </li>
                ))}
              </ul>
            </div>
            {i < TIERS.length - 1 && <Connector />}
          </div>
        ))}
      </div>

      {/* pipeline */}
      <div className="reveal">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="font-display text-xs font-semibold uppercase tracking-[0.25em] text-brand-300">Inside /api/plan</p>
            <h3 className="font-display text-2xl font-semibold text-white">The 10-stage planning pipeline</h3>
          </div>
          <p className="text-xs text-slate-400">{auto ? "Auto-playing — tap a stage to take control" : "Tap any stage"}</p>
        </div>
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {STAGES.map((s, i) => {
            const on = i === stage;
            const done = i < stage;
            return (
              <li key={s.name}>
                <button
                  type="button"
                  onClick={() => (setAuto(false), setStage(i))}
                  aria-pressed={on}
                  className={`group flex w-full items-center gap-2.5 rounded-2xl p-2.5 text-left ring-1 transition duration-300 ${
                    on
                      ? "bg-brand-400/15 ring-brand-300/60 shadow-[0_0_24px_rgba(52,207,174,0.25)]"
                      : done
                        ? "bg-white/[0.05] ring-white/10 hover:bg-white/10"
                        : "bg-white/[0.02] ring-white/5 hover:bg-white/[0.06]"
                  }`}
                >
                  <span
                    className={`hex flex h-9 w-10 shrink-0 items-center justify-center text-base transition ${
                      on ? "animate-bob bg-gradient-to-br from-brand-300 to-cyan-500" : done ? "bg-brand-400/30" : "bg-white/10"
                    }`}
                  >
                    {s.icon}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-display text-[10px] font-semibold tracking-[0.2em] text-slate-500">STAGE {i + 1}</span>
                    <span className={`block truncate font-display text-sm font-semibold ${on ? "text-white" : "text-slate-300"}`}>{s.name}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <div key={stage} className="panel mt-3 animate-fade-up rounded-2xl p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-display text-lg font-semibold text-white">
              <span aria-hidden className="mr-2">
                {cur.icon}
              </span>
              {stage + 1}. {cur.name}
            </p>
            <code className="rounded-lg bg-black/40 px-2 py-1 font-mono text-[11px] text-brand-200 ring-1 ring-white/10">backend/app/{cur.file}</code>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{cur.detail}</p>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-black/40">
            <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-cyan-400 transition-[width] duration-500" style={{ width: `${((stage + 1) / STAGES.length) * 100}%` }} />
          </div>
        </div>
      </div>

      {/* fallback chains */}
      <div className="reveal">
        <p className="font-display text-xs font-semibold uppercase tracking-[0.25em] text-brand-300">Extra lives</p>
        <h3 className="mb-1 font-display text-2xl font-semibold text-white">Every provider has a fallback</h3>
        <p className="mb-4 max-w-2xl text-sm text-slate-400">
          Free services rate-limit and go down. Each chain tries left to right, remembers failures (a bad OneMap login backs off for 15 minutes), and the
          cache is keyed by provider so one never shadows another.
        </p>
        <div className="space-y-2">
          {CHAINS.map((c) => (
            <div key={c.label} className="card flex flex-col gap-2 p-3 sm:flex-row sm:items-center">
              <p className="w-36 shrink-0 font-display font-semibold text-white">
                <span aria-hidden className="mr-1.5">
                  {c.icon}
                </span>
                {c.label}
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                {c.items.map((x, i) => (
                  <span key={x} className="flex items-center gap-1.5">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                        i === 0 ? "bg-brand-400/15 text-brand-100 ring-brand-300/40" : "bg-white/5 text-slate-300 ring-white/10"
                      }`}
                    >
                      {i === 0 && <span className="mr-1 text-[10px]">❤</span>}
                      {x}
                    </span>
                    {i < c.items.length - 1 && <span className="text-slate-600">→</span>}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
