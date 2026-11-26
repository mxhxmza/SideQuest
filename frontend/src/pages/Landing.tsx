import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import Logo from "../components/Logo";
import Architecture from "../components/landing/Architecture";
import HeroMap from "../components/landing/HeroMap";
import PromptDemo from "../components/landing/PromptDemo";
import ScoreDemo, { RULES } from "../components/landing/ScoreDemo";
import { BADGES } from "../lib/game";
import { linkTo } from "../lib/router";
import { useRevealAll, useSeen } from "../lib/useReveal";

const STEPS = [
  { icon: "📍", title: "Set start & finish", body: "Pick where you're leaving from and where you're headed — any address, MRT station or landmark in Singapore." },
  { icon: "📜", title: "Type your side quests", body: "Write it like a text: “mosque at Asar, halal ice cream, petrol”. Watch it turn into a quest log as you type." },
  { icon: "🧭", title: "Get the best stops", body: "For every quest, places along the way ranked by the extra minutes they add — checked against real routing." },
  { icon: "⭐", title: "Earn stars, then go", body: "Low detours earn stars and XP. Tap once to open the whole trip in Google Maps." },
];

const POWERUPS = [
  { icon: "🕌", title: "Prayer-aware", body: "MUIS prayer times along your route. See where you'll be when Asar begins and land a mosque inside the window.", tint: "from-amber-300/25" },
  { icon: "⏱️", title: "Minutes, not kilometres", body: "Every option shows how many minutes it adds to your trip — the number that actually matters.", tint: "from-brand-300/25" },
  { icon: "🕐", title: "Open when you arrive", body: "Opening hours are checked at your ETA, not right now. A café that closes before you get there loses.", tint: "from-cyan-300/25" },
  { icon: "🥘", title: "Halal · veg · vegan", body: "Dietary tags from OpenStreetMap. Weak hints are flagged and never passed off as certified.", tint: "from-emerald-300/25" },
  { icon: "⚡", title: "Combo stops", body: "Two quests in the same mall or shop merge into one stop — zero extra minutes.", tint: "from-violet-300/25" },
  { icon: "📌", title: "Pin & re-plan", body: "Prefer the second option? Pin it and the rest of the trip re-plans around your choice.", tint: "from-pink-300/25" },
  { icon: "🚇", title: "Four ways to travel", body: "Drive, public transport, walk or cycle. Transit shows where to hop off for each stop.", tint: "from-sky-300/25" },
  { icon: "🚀", title: "Google Maps hand-off", body: "Your stops become waypoints in one link. Transit gets a link per leg.", tint: "from-blue-300/25" },
];

const STACK = [
  "Python 3.11",
  "FastAPI",
  "Pydantic v2",
  "httpx",
  "SQLite R*Tree",
  "osmium",
  "adhanpy",
  "opening-hours",
  "React 18",
  "TypeScript",
  "Vite",
  "Tailwind v4",
  "MapLibre GL",
  "OpenFreeMap",
  "OneMap",
  "OSRM",
  "Photon",
  "PWA",
];

const GLITCHES = [
  ["🥘", "Halal tags are sparse in OpenStreetMap, and MUIS certification isn't there at all — places without evidence are labelled “unverified”."],
  ["🕐", "Many places have no opening hours mapped, so “hours unknown” shows up a lot (and costs 3 points)."],
  ["🚇", "Google Maps won't take waypoints for public transport, so transit trips get one link per leg."],
  ["😴", "The free server sleeps when idle — the first plan of the day can take about a minute."],
];

function SectionTitle({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <div className="reveal mx-auto mb-10 max-w-2xl text-center">
      <p className="font-display text-xs font-semibold uppercase tracking-[0.3em] text-brand-300">{kicker}</p>
      <h2 className="mt-2 font-logo text-3xl leading-tight text-white sm:text-4xl">{title}</h2>
      {children && <p className="mt-3 text-slate-400">{children}</p>}
    </div>
  );
}

function PlayButton({ big, label = "Press start" }: { big?: boolean; label?: string }) {
  return (
    <a href="/plan" onClick={linkTo("/plan")} className={`btn-3d ${big ? "px-8 py-4 text-lg" : ""}`}>
      ▶ {label}
    </a>
  );
}

export default function Landing() {
  const page = useRevealAll<HTMLDivElement>();
  const [demoRef, demoSeen] = useSeen<HTMLDivElement>();
  const [poiCount, setPoiCount] = useState<number | null>(null);

  // live numbers from the server, if it's awake (never blocks the page)
  useEffect(() => {
    let live = true;
    api
      .health(8000)
      .then((h) => {
        const n = Number(h.poi_db.poi_count);
        if (live && Number.isFinite(n) && n > 0) setPoiCount(n);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    document.title = "SideQuest · Route-aware stop planner";
  }, []);

  return (
    <div ref={page} className="relative min-h-dvh overflow-x-hidden bg-ink-950 text-slate-100">
      {/* nav */}
      <nav className="fixed inset-x-0 top-0 z-40 border-b border-white/5 bg-ink-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <a href="/" onClick={linkTo("/")} aria-label="SideQuest home">
            <Logo />
          </a>
          <div className="hidden items-center gap-6 font-display text-sm font-medium text-slate-300 md:flex">
            <a href="#how" className="transition hover:text-white">
              How to play
            </a>
            <a href="#powerups" className="transition hover:text-white">
              Power-ups
            </a>
            <a href="#engine" className="transition hover:text-white">
              Architecture
            </a>
            <a href="#scoring" className="transition hover:text-white">
              Scoring
            </a>
          </div>
          <a href="/plan" onClick={linkTo("/plan")} className="btn-3d px-4 py-2 text-xs">
            ▶ Play
          </a>
        </div>
      </nav>

      {/* hero */}
      <header className="relative overflow-hidden pb-20 pt-28 sm:pt-32">
        <div className="aurora" />
        <div className="stars" />
        <div className="grid-floor" />
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent to-ink-950" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-[1.05fr_1fr]">
          <div className="text-center lg:text-left">
            <p className="inline-flex animate-fade-up items-center gap-2 rounded-full bg-white/5 px-3 py-1 font-display text-xs font-semibold tracking-wide text-slate-300 ring-1 ring-white/10">
              <span className="relative flex h-2 w-2">
                <span className="absolute inset-0 animate-ping-slow rounded-full bg-emerald-400" />
                <span className="relative h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              Singapore edition · free · no sign-up
            </p>
            <h1 className="mt-5 animate-fade-up font-logo text-[42px] leading-[1.02] text-white sm:text-6xl" style={{ animationDelay: "80ms" }}>
              Turn errands into <span className="text-gradient">side quests</span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl animate-fade-up text-lg leading-relaxed text-slate-300 lg:mx-0" style={{ animationDelay: "160ms" }}>
              Say where you're going and what you need on the way — a mosque at Asar, halal ice cream, petrol. SideQuest finds the stops that add the{" "}
              <b className="text-white">fewest minutes</b> to your trip, then hands the route to Google Maps.
            </p>
            <div className="mt-8 flex animate-fade-up flex-wrap items-center justify-center gap-4 lg:justify-start" style={{ animationDelay: "240ms" }}>
              <PlayButton big />
              <a href="#how" className="btn-ghost px-5 py-3.5 font-display font-semibold tracking-wide">
                How it works ↓
              </a>
            </div>
            <dl className="mt-10 grid animate-fade-up grid-cols-3 gap-3 text-center lg:max-w-md" style={{ animationDelay: "320ms" }}>
              {[
                [poiCount ? `${Math.round(poiCount / 1000)}k` : "OSM", poiCount ? "places mapped" : "places data"],
                ["5", "daily prayers"],
                ["$0", "to run"],
              ].map(([v, l]) => (
                <div key={l} className="rounded-2xl bg-white/[0.04] px-2 py-3 ring-1 ring-white/10">
                  <dt className="sr-only">{l}</dt>
                  <dd className="font-logo text-2xl text-white">{v}</dd>
                  <dd className="text-[11px] uppercase tracking-wider text-slate-400">{l}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="relative mx-auto w-full max-w-[540px] animate-fade-up" style={{ animationDelay: "200ms" }}>
            <div aria-hidden className="absolute -inset-6 rounded-[40px] bg-gradient-to-br from-brand-400/20 via-cyan-400/10 to-violet-500/20 blur-2xl" />
            <div className="relative animate-float">
              <HeroMap />
            </div>
            <div className="absolute -bottom-4 left-4 animate-bob rounded-2xl bg-amber-400/15 px-3 py-2 font-logo text-sm text-amber-200 ring-1 ring-amber-300/40 backdrop-blur sm:left-8">
              +217 XP
            </div>
          </div>
        </div>
      </header>

      {/* talk like a human */}
      <section className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div className="reveal">
            <p className="font-display text-xs font-semibold uppercase tracking-[0.3em] text-brand-300">No forms. Just type.</p>
            <h2 className="mt-2 font-logo text-3xl leading-tight text-white sm:text-4xl">It understands your quest log</h2>
            <p className="mt-4 text-slate-300">
              Times (“around 1pm”, “45 min in”, “at Asar”), diets (“halal”, “vegetarian”), and 20+ kinds of places — mosques, hawker centres, petrol, ATMs,
              pharmacies, toilets and more. Anything it doesn't recognise becomes a name search, and you're told about it instead of it silently vanishing.
            </p>
            <ul className="mt-5 space-y-2 text-sm text-slate-300">
              {["Parses live as you type — tap any quest to tweak it", "Works without an AI model; plug in a local LLM if you like", "Every quest gets its own time window on your route"].map(
                (x) => (
                  <li key={x} className="flex gap-2">
                    <span className="text-brand-300">✦</span>
                    {x}
                  </li>
                ),
              )}
            </ul>
          </div>
          <div ref={demoRef} className="reveal">
            <PromptDemo active={demoSeen} />
          </div>
        </div>
      </section>

      {/* how to play */}
      <section id="how" className="relative scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionTitle kicker="How to play" title="Four levels to a better trip" />
        <ol className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="reveal card group relative overflow-hidden p-5 transition duration-300 hover:-translate-y-1.5 hover:border-brand-300/40" style={{ transitionDelay: `${i * 90}ms` }}>
              <span aria-hidden className="absolute -right-3 -top-6 font-logo text-[96px] leading-none text-white/[0.04]">
                {i + 1}
              </span>
              <span className="hex flex h-12 w-14 items-center justify-center bg-gradient-to-br from-brand-300 to-cyan-500 text-2xl transition group-hover:animate-wiggle">
                {s.icon}
              </span>
              <p className="mt-4 font-display text-[11px] font-semibold tracking-[0.25em] text-brand-300">LEVEL {i + 1}</p>
              <p className="font-display text-lg font-semibold text-white">{s.title}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* power-ups */}
      <section id="powerups" className="relative scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionTitle kicker="Power-ups" title="What it knows that a map app doesn't">
          Built for real Singapore errands — prayer times, opening hours and dietary needs are part of the plan, not an afterthought.
        </SectionTitle>
        <div className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {POWERUPS.map((p, i) => (
            <div
              key={p.title}
              className={`reveal group relative overflow-hidden rounded-2xl bg-gradient-to-b ${p.tint} to-transparent p-[1px] transition duration-300 hover:-translate-y-1`}
              style={{ transitionDelay: `${(i % 4) * 80}ms` }}
            >
              <div className="h-full rounded-2xl bg-ink-900/95 p-5">
                <span className="text-3xl transition duration-300 group-hover:scale-125 group-hover:animate-wiggle inline-block" aria-hidden>
                  {p.icon}
                </span>
                <p className="mt-3 font-display text-lg font-semibold text-white">{p.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-400">{p.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* architecture */}
      <section id="engine" className="relative scroll-mt-20 overflow-hidden px-4 py-20 sm:px-6">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/40 to-transparent" />
        <SectionTitle kicker="Under the hood" title="The game engine">
          A small, honest architecture: a static PWA, one Python API, and free data sources — each with a fallback.
        </SectionTitle>
        <div className="mx-auto max-w-6xl">
          <Architecture />
        </div>
      </section>

      {/* scoring */}
      <section id="scoring" className="relative scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionTitle kicker="Scoring rules" title="Lowest score wins">
          Every option gets a score in minutes: the real detour plus penalties for things that could ruin the stop. Tap “Why this rank?” in the app to see
          any option's breakdown.
        </SectionTitle>
        <div className="mx-auto grid max-w-6xl items-start gap-8 lg:grid-cols-[1.2fr_1fr]">
          <div className="reveal">
            <p className="mb-3 font-display text-sm font-semibold text-slate-300">
              Example: <span className="text-white">“halal ice cream”</span> — three candidates
            </p>
            <ScoreDemo />
            <p className="mt-3 text-xs text-slate-500">Illustrative places; the penalty values are the ones the planner uses.</p>
          </div>
          <div className="reveal card p-5">
            <p className="mb-3 font-display text-lg font-semibold text-white">📖 The rulebook</p>
            <dl className="divide-y divide-white/5 text-sm">
              {RULES.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 py-2">
                  <dt className="text-slate-300">{k}</dt>
                  <dd className="text-right font-mono text-xs text-brand-200">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 rounded-xl bg-amber-400/10 p-3 text-xs text-amber-100 ring-1 ring-amber-300/25">
              <b className="font-display tracking-wide">⭐ Stars:</b> 1 for a route, 2 when every quest is found, 3 when it also costs ≤ 5 extra minutes per stop.
            </div>
          </div>
        </div>
      </section>

      {/* badges preview */}
      <section className="relative px-4 py-20 sm:px-6">
        <SectionTitle kicker="Collectibles" title={`${BADGES.length} badges to unlock`}>
          Earned from real trips — no grinding required. Progress lives in your browser.
        </SectionTitle>
        <div className="mx-auto flex max-w-4xl flex-wrap justify-center gap-3">
          {BADGES.map((b, i) => (
            <div key={b.id} className="reveal group flex flex-col items-center gap-1.5" style={{ transitionDelay: `${(i % 8) * 50}ms` }} title={b.desc}>
              <span className="hex flex h-14 w-16 items-center justify-center bg-gradient-to-br from-amber-200 via-amber-400 to-orange-500 text-2xl transition duration-300 group-hover:-translate-y-1 group-hover:scale-110">
                {b.icon}
              </span>
              <span className="max-w-[84px] text-center font-display text-[11px] font-medium leading-tight text-slate-400 group-hover:text-white">{b.name}</span>
            </div>
          ))}
        </div>
      </section>

      {/* stack + glitches */}
      <section className="relative px-4 py-20 sm:px-6">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-2">
          <div className="reveal card p-6">
            <p className="font-display text-xs font-semibold uppercase tracking-[0.3em] text-brand-300">Free to play</p>
            <h3 className="mt-1 font-display text-2xl font-semibold text-white">A $0 stack, no card needed</h3>
            <p className="mt-2 text-sm text-slate-400">
              The API runs on a free Render instance, the web app on Vercel. Map tiles from OpenFreeMap, places from OpenStreetMap, routing from OneMap with
              keyless fallbacks.
            </p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {STACK.map((s) => (
                <span key={s} className="rounded-lg bg-white/5 px-2.5 py-1 font-mono text-xs text-slate-300 ring-1 ring-white/10">
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div className="reveal card p-6">
            <p className="font-display text-xs font-semibold uppercase tracking-[0.3em] text-rose-300">Known glitches</p>
            <h3 className="mt-1 font-display text-2xl font-semibold text-white">What it can't do (yet)</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              {GLITCHES.map(([i, t]) => (
                <li key={t} className="flex gap-3">
                  <span aria-hidden className="text-lg">
                    {i}
                  </span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* final CTA */}
      <section className="relative overflow-hidden px-4 py-24 text-center sm:px-6">
        <div aria-hidden className="fade-edges pointer-events-none absolute inset-0">
          <div className="aurora opacity-70" />
        </div>
        <div className="reveal relative mx-auto max-w-2xl">
          <p className="animate-blink font-display text-sm font-semibold uppercase tracking-[0.4em] text-amber-300">Insert coin — it's free</p>
          <h2 className="mt-3 font-logo text-4xl leading-tight text-white sm:text-5xl">
            Your next trip is a <span className="text-gradient">quest</span>
          </h2>
          <div className="mt-8">
            <PlayButton big label="Start your quest" />
          </div>
        </div>
      </section>

      <footer className="border-t border-white/5 px-4 py-8 text-center text-xs text-slate-500 sm:px-6">
        <p>
          Map data ©{" "}
          <a className="underline hover:text-slate-300" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
            OpenStreetMap contributors
          </a>{" "}
          · Tiles by{" "}
          <a className="underline hover:text-slate-300" href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">
            OpenFreeMap
          </a>{" "}
          · Routing &amp; search by OneMap (SLA) · Prayer times computed with the MUIS method
        </p>
        <p className="mt-2">SideQuest never claims halal certification — check MUIS on site.</p>
      </footer>
    </div>
  );
}
