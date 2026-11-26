import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import Handoff from "./components/Handoff";
import MapView from "./components/MapView";
import ModeSwitch, { MODES } from "./components/ModeSwitch";
import PlaceInput from "./components/PlaceInput";
import PlanningOverlay from "./components/PlanningOverlay";
import PromptBox from "./components/PromptBox";
import StopDetail from "./components/StopDetail";
import SummaryCard from "./components/SummaryCard";
import Timeline from "./components/Timeline";
import { fmtDay, fmtTime, inputToIso, localInputNow } from "./lib/format";
import type { Category, Health, Mode, Point, StopRequest, TripPlan } from "./types";

type ServerState = "checking" | "waking" | "ok" | "down";

function useMediaQuery(q: string): boolean {
  const [m, setM] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return m;
}

export default function App() {
  const [origin, setOrigin] = useState<Point | null>(null);
  const [destination, setDestination] = useState<Point | null>(null);
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [mode, setMode] = useState<Mode>("drive");
  const [depart, setDepart] = useState(localInputNow());
  const [text, setText] = useState("");
  const [stops, setStops] = useState<StopRequest[]>([]);
  const [unrecognized, setUnrecognized] = useState<string[]>([]);
  const [parsedText, setParsedText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [pinned, setPinned] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [server, setServer] = useState<ServerState>("checking");
  const [health, setHealth] = useState<Health | null>(null);
  const [showForm, setShowForm] = useState(true);
  const resultsRef = useRef<HTMLDivElement>(null);
  const desktop = useMediaQuery("(min-width: 1024px)");

  // wake the (possibly sleeping) backend on load — free hosting cold starts take ~1 min
  useEffect(() => {
    let done = false;
    const slow = setTimeout(() => !done && setServer("waking"), 2500);
    api
      .health()
      .then((h) => {
        setHealth(h);
        setServer("ok");
        return api.categories().then(setCategories);
      })
      .catch(() => setServer("down"))
      .finally(() => {
        done = true;
        clearTimeout(slow);
      });
    return () => clearTimeout(slow);
  }, []);

  // understand the request while the user types (debounced)
  useEffect(() => {
    if (!text.trim()) {
      setStops([]);
      setUnrecognized([]);
      setParsedText("");
      return;
    }
    if (text === parsedText) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setParsing(true);
      try {
        const r = await api.parse(text, inputToIso(depart), ctrl.signal);
        setStops(r.stops);
        setUnrecognized(r.unrecognized ?? []);
        setParsedText(text);
        setPinned({});
      } catch {
        /* aborted or offline: planning parses again */
      } finally {
        setParsing(false);
      }
    }, 450);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const runPlan = useCallback(
    async (opts?: { stops?: StopRequest[]; pinned?: Record<string, string> }) => {
      setError(null);
      // a place typed but not picked from the list: use the best match for that text
      const resolve = async (p: Point | null, typedText: string, set: (p: Point) => void, label: string) => {
        if (p) return p;
        const q = typedText.trim();
        if (q.length < 2) throw new Error(`Where are you ${label === "start" ? "starting from" : "going"}?`);
        const r = await api.geocode(q);
        if (!r.length) throw new Error(`Couldn't find “${q}” — try another name for the ${label}.`);
        const best = { lat: r[0].lat, lng: r[0].lng, name: r[0].name };
        set(best);
        return best;
      };
      let from: Point, to: Point;
      try {
        from = await resolve(origin, originText, setOrigin, "start");
        to = await resolve(destination, destText, setDestination, "destination");
      } catch (e) {
        setError((e as Error).message);
        return;
      }
      setBusy(true);
      try {
        let s = opts?.stops ?? stops;
        if (!opts?.stops && text.trim() && text !== parsedText) {
          const r = await api.parse(text, inputToIso(depart));
          s = r.stops;
          setStops(r.stops);
          setUnrecognized(r.unrecognized ?? []);
          setParsedText(text);
        }
        const p = await api.plan({
          origin: from,
          destination: to,
          mode,
          departure_time: inputToIso(depart),
          stops: s,
          pinned: opts?.pinned ?? pinned,
        });
        setPlan(p);
        setShowForm(false);
        setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : (e as Error).message;
        setError(e instanceof ApiError && e.status === 502 ? `Routing failed: ${msg}` : msg);
      } finally {
        setBusy(false);
      }
    },
    [origin, destination, originText, destText, mode, depart, stops, pinned, text, parsedText],
  );

  const pin = useCallback(
    (stopId: string, osmId: string) => {
      const next = { ...pinned, [stopId]: osmId };
      setPinned(next);
      runPlan({ pinned: next });
    },
    [pinned, runPlan],
  );

  const suggestMosque = (prayer: string) => {
    const n = Math.max(0, ...stops.map((s) => Number(s.id.replace(/\D/g, "")) || 0)) + 1;
    const s: StopRequest = {
      id: `s${n}`,
      query: `mosque at ${prayer}`,
      category: "mosque",
      time_window: { type: "prayer", value: prayer, relation: "at" },
      constraints: { open_at_eta: true, dietary: [] },
    };
    const next = [...stops, s];
    setStops(next);
    setSelected(s.id);
    runPlan({ stops: next });
  };

  const swap = () => {
    setOrigin(destination);
    setDestination(origin);
    setOriginText(destText);
    setDestText(originText);
  };

  const transitUnavailable = health && health.routing.transit.length === 0;
  const modeInfo = MODES.find((m) => m.key === mode);

  return (
    <div className="flex h-full flex-col lg:relative lg:block">
      {/* map: top on mobile, full-bleed behind the panel on desktop */}
      <div className="relative h-[38vh] shrink-0 lg:absolute lg:inset-0 lg:h-auto">
        <MapView
          plan={plan}
          origin={origin}
          destination={destination}
          selectedStopId={selected}
          onSelectStop={setSelected}
          onPickCandidate={pin}
          padLeft={desktop ? 500 : 0}
        />
        {busy && <PlanningOverlay />}
      </div>

      <aside className="relative z-10 -mt-6 flex min-h-0 flex-1 flex-col rounded-t-3xl bg-white shadow-[0_-12px_40px_rgba(15,23,42,0.12)] lg:absolute lg:bottom-4 lg:left-4 lg:top-4 lg:mt-0 lg:w-[460px] lg:rounded-3xl lg:bg-white/85 lg:shadow-2xl lg:ring-1 lg:ring-black/5 lg:backdrop-blur-xl">
        <header className="flex items-center justify-between px-5 pb-3 pt-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500 shadow-lg shadow-brand-500/30">
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
                <path d="M5 19c4-1 3-7 7-8s5-6 7-6" />
                <circle cx="5" cy="19" r="2" fill="white" />
                <circle cx="12" cy="11" r="2" fill="#fde68a" stroke="#fde68a" />
                <circle cx="19" cy="5" r="2" fill="white" />
              </svg>
            </span>
            <div>
              <h1 className="text-lg font-extrabold leading-tight tracking-tight text-slate-900">Stop Planner</h1>
              <p className="text-xs text-slate-500">Stops ranked by minutes added · Singapore</p>
            </div>
          </div>
          <ServerBadge state={server} health={health} />
        </header>

        {server === "waking" && (
          <div className="mx-5 mb-2 animate-fade-up rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-amber-200">
            Waking the server… free hosting sleeps after 15 minutes idle and takes about a minute to start.
          </div>
        )}
        {server === "down" && (
          <div className="mx-5 mb-2 animate-fade-up rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-800 ring-1 ring-rose-200">
            Can't reach the planner server.{" "}
            <button className="font-semibold underline" onClick={() => location.reload()}>
              Retry
            </button>
          </div>
        )}

        <div className="scroll-soft min-h-0 flex-1 space-y-4 overflow-y-auto px-5 pb-8">
          {!showForm && plan ? (
            <button
              type="button"
              className="flex w-full animate-fade-up items-center justify-between gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-left text-sm ring-1 ring-slate-200 transition hover:bg-white hover:shadow-md"
              onClick={() => setShowForm(true)}
            >
              <span className="min-w-0">
                <span className="block truncate font-bold text-slate-800">
                  {origin?.name} <span className="text-slate-400">→</span> {destination?.name}
                </span>
                <span className="text-xs text-slate-500">
                  {modeInfo?.icon} {modeInfo?.label} · {fmtDay(plan.departure_time)} {fmtTime(plan.departure_time)}
                </span>
              </span>
              <span className="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-bold text-brand-700 shadow-sm">Edit</span>
            </button>
          ) : (
            <form
              className="animate-fade-up space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                runPlan();
              }}
            >
              <div className="relative space-y-2">
                <span aria-hidden className="absolute left-[21px] top-[30px] h-[34px] border-l-2 border-dashed border-slate-300" />
                <PlaceInput
                  label="From"
                  dot="origin"
                  value={origin}
                  onChange={setOrigin}
                  onText={setOriginText}
                  placeholder="Starting point — e.g. NTU"
                  allowLocate
                />
                <PlaceInput
                  label="To"
                  dot="dest"
                  value={destination}
                  onChange={setDestination}
                  onText={setDestText}
                  placeholder="Destination — e.g. Changi Airport"
                />
                <button
                  type="button"
                  onClick={swap}
                  title="Swap start and destination"
                  aria-label="Swap start and destination"
                  className="absolute -right-2 top-1/2 z-20 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-white text-slate-500 shadow-md ring-1 ring-slate-200 transition duration-300 hover:rotate-180 hover:text-brand-600"
                >
                  ⇅
                </button>
              </div>

              <div className="grid grid-cols-[1fr_auto] items-end gap-3">
                <label className="block">
                  <span className="lbl">Leave at</span>
                  <input className="input" type="datetime-local" value={depart} onChange={(e) => setDepart(e.target.value)} required />
                </label>
                <button
                  type="button"
                  className="btn-ghost h-[42px] px-3 text-xs font-semibold"
                  onClick={() => setDepart(localInputNow())}
                >
                  Now
                </button>
              </div>

              <ModeSwitch value={mode} onChange={setMode} />
              {mode === "transit" && transitUnavailable && (
                <p className="animate-fade-up text-xs text-amber-700">
                  {health?.onemap_error
                    ? `Public transport is unavailable: ${health.onemap_error}`
                    : "Public transport needs OneMap credentials on the server."}
                </p>
              )}

              <PromptBox
                text={text}
                onText={setText}
                stops={stops}
                onStops={(s) => (setStops(s), setPinned({}))}
                unrecognized={unrecognized}
                categories={categories}
                parsing={parsing}
              />

              <button type="submit" className="btn-primary w-full py-3.5 text-base" disabled={busy || server === "down"}>
                {busy ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> Planning…
                  </>
                ) : (
                  <>Plan my trip →</>
                )}
              </button>

              {!plan && !text && (
                <ol className="grid grid-cols-3 gap-2 pt-1 text-center text-[11px] text-slate-500">
                  {[
                    ["📍", "Set start & destination"],
                    ["💬", "Say what you need"],
                    ["⏱️", "Get stops ranked by minutes added"],
                  ].map(([i, t], k) => (
                    <li key={t} className="animate-fade-up rounded-2xl bg-slate-50 px-2 py-3" style={{ animationDelay: `${150 + k * 90}ms` }}>
                      <span className="mb-1 block text-lg">{i}</span>
                      {t}
                    </li>
                  ))}
                </ol>
              )}
            </form>
          )}

          {error && (
            <div role="alert" className="animate-pop rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-200">
              {error}
            </div>
          )}

          {plan && (
            <div ref={resultsRef} key={plan.arrival_eta + plan.total_added_min} className="space-y-4 pt-1">
              <SummaryCard plan={plan} />
              {plan.warnings.map((w) => (
                <p key={w} className="animate-fade-up rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-amber-200">
                  ⚠ {w}
                </p>
              ))}
              <Timeline
                plan={plan}
                selectedStopId={selected}
                onSelectStop={setSelected}
                onSuggestMosque={suggestMosque}
                renderDetail={(id) => {
                  const sp = plan.stops.find((s) => s.request.id === id);
                  return sp ? <StopDetail stop={sp} busy={busy} onUse={(osm) => pin(id, osm)} /> : null;
                }}
              />
              {origin && destination && <Handoff plan={plan} origin={origin} destination={destination} />}
              <DataNotes plan={plan} health={health} />
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function ServerBadge({ state, health }: { state: ServerState; health: Health | null }) {
  const dot = { checking: "bg-slate-300", waking: "bg-amber-400", ok: "bg-emerald-500", down: "bg-rose-500" }[state];
  const title = health
    ? `Routing: ${Object.entries(health.routing)
        .map(([m, p]) => `${m}=${p.join("/") || "none"}`)
        .join(", ")} · POIs ${health.poi_db.poi_count ?? "?"} (OSM ${health.poi_db.data_timestamp?.slice(0, 10) ?? "?"})`
    : state;
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600" title={title}>
      <span className="relative flex h-2 w-2">
        {state === "ok" && <span className={`absolute inset-0 animate-ping-slow rounded-full ${dot}`} />}
        <span className={`relative h-2 w-2 rounded-full ${dot}`} />
      </span>
      {state === "ok" ? "Online" : state === "checking" ? "Connecting" : state === "waking" ? "Waking" : "Offline"}
    </span>
  );
}

function DataNotes({ plan, health }: { plan: TripPlan; health: Health | null }) {
  return (
    <details className="group rounded-2xl bg-slate-50 p-4 text-xs text-slate-600 ring-1 ring-slate-200">
      <summary className="cursor-pointer list-none font-semibold text-slate-700">
        <span className="mr-1 inline-block transition group-open:rotate-90">›</span> About this data
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>
          Route by <b>{plan.route.provider}</b>. Detours marked “est.” are estimates; the top options per stop are checked with real
          routing.
        </li>
        <li>
          Places come from OpenStreetMap{health?.poi_db.data_timestamp ? ` (data as of ${health.poi_db.data_timestamp.slice(0, 10)})` : ""}.
          Halal tags are sparse and MUIS certification isn't in OSM: “?” badges are hints, not facts. This app never claims certification.
        </li>
        <li>Many places have no opening hours in OSM, so “hours unknown” is common. Mall prayer rooms are rarely mapped.</li>
        <li>Prayer times use the MUIS method, computed at your starting point.</li>
      </ul>
    </details>
  );
}
