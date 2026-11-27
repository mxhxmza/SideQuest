import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { PlacePreview, Point, TripPlan } from "../types";
import { addedMin, fmtTime, PRAYER_LABEL } from "../lib/format";

const STYLE = "https://tiles.openfreemap.org/styles/fiord";
const SG_CENTER: [number, number] = [103.8198, 1.3521];
const LEG_COLORS: Record<string, string> = {
  WALK: "#cbd5e1",
  BUS: "#4ade80",
  SUBWAY: "#c084fc",
  RAIL: "#c084fc",
  TRAM: "#22d3ee",
};
const ROUTE_COLOR = "#5eead4";
const DRAW_MS = 2000;

type LngLat = [number, number];
interface Part {
  f: Feature;
  cum: number[];
  start: number;
  len: number;
}

/** metres-ish distance; only used to pace the draw animation */
function dist(a: LngLat, b: LngLat): number {
  const kx = 111_320 * Math.cos((a[1] * Math.PI) / 180);
  return Math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * 110_540);
}

function prepare(features: Feature[]): { parts: Part[]; total: number } {
  let off = 0;
  const parts = features.map((f) => {
    const c = f.geometry.coordinates as LngLat[];
    const cum = [0];
    for (let i = 1; i < c.length; i++) cum.push(cum[i - 1] + dist(c[i - 1], c[i]));
    const p = { f, cum, start: off, len: cum[cum.length - 1] };
    off += p.len;
    return p;
  });
  return { parts, total: off };
}

/** The route drawn up to distance d, plus the point at its head (the "player"). */
function cut(parts: Part[], d: number): { features: Feature[]; head: LngLat | null } {
  const out: Feature[] = [];
  let head: LngLat | null = null;
  for (const p of parts) {
    if (d <= p.start && out.length) break;
    const c = p.f.geometry.coordinates as LngLat[];
    const local = d - p.start;
    if (local >= p.len) {
      out.push(p.f);
      head = c[c.length - 1];
      continue;
    }
    let i = 1;
    while (i < c.length - 1 && p.cum[i] < local) i++;
    const seg = p.cum[i] - p.cum[i - 1] || 1;
    const t = Math.max(0, Math.min(1, (local - p.cum[i - 1]) / seg));
    const pt: LngLat = [c[i - 1][0] + (c[i][0] - c[i - 1][0]) * t, c[i - 1][1] + (c[i][1] - c[i - 1][1]) * t];
    const coords = [...c.slice(0, i), pt];
    if (coords.length >= 2) out.push({ ...p.f, geometry: { ...p.f.geometry, coordinates: coords } });
    head = pt;
    break;
  }
  return { features: out, head };
}

const pointFC = (pt: LngLat | null): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: pt ? [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: pt } }] : [],
});

interface Props {
  plan: TripPlan | null;
  origin: Point | null;
  destination: Point | null;
  selectedStopId: string | null;
  onSelectStop: (id: string) => void;
  onPickCandidate?: (stopId: string, osmId: string) => void;
  /** px of map covered by the floating panel on the left (desktop) */
  padLeft?: number;
  /** suggestions for the Start / Finish box being typed in */
  preview?: PlacePreview | null;
}

type Feature = GeoJSON.Feature<GeoJSON.LineString, { mode: string; color: string }>;

function el(cls: string, html: string, title?: string): HTMLElement {
  const d = document.createElement("div");
  d.className = cls;
  d.innerHTML = html;
  if (title) d.title = title;
  return d;
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function MapView({
  plan,
  origin,
  destination,
  selectedStopId,
  onSelectStop,
  onPickCandidate,
  padLeft = 0,
  preview = null,
}: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const candMarkers = useRef<maplibregl.Marker[]>([]);
  const prayerMarkers = useRef<maplibregl.Marker[]>([]);
  const anim = useRef<number | null>(null);

  // init
  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({
      container: box.current,
      style: STYLE,
      center: SG_CENTER,
      zoom: 10.6,
      attributionControl: false,
    });
    m.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution:
          '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      }),
      "bottom-right",
    );
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      // small screens: start the attribution collapsed behind its (i) button
      if (window.matchMedia("(max-width: 640px)").matches)
        box.current?.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
      m.addSource("route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "route-glow",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 18, "line-opacity": 0.35, "line-blur": 8 },
      });
      m.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#050816", "line-width": 9, "line-opacity": 0.9 },
      });
      m.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        filter: ["!=", ["get", "mode"], "WALK"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 5.5 },
      });
      m.addLayer({
        id: "route-walk",
        type: "line",
        source: "route",
        filter: ["==", ["get", "mode"], "WALK"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": LEG_COLORS.WALK, "line-width": 4, "line-dasharray": [1, 1.6] },
      });
      m.addSource("player", { type: "geojson", data: pointFC(null) });
      m.addLayer({
        id: "player-halo",
        type: "circle",
        source: "player",
        paint: { "circle-radius": 16, "circle-color": "#5eead4", "circle-opacity": 0.3, "circle-blur": 0.6 },
      });
      m.addLayer({
        id: "player-dot",
        type: "circle",
        source: "player",
        paint: { "circle-radius": 6.5, "circle-color": "#ffffff", "circle-stroke-width": 3, "circle-stroke-color": "#34cfae" },
      });
      ready.current = true;
      pending.current?.();
      pending.current = null;
    });
    map.current = m;
    // the panel changes size (plan appears, window resizes, mobile layout) — keep the canvas in sync
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      if (anim.current) cancelAnimationFrame(anim.current);
      ready.current = false;
      m.remove();
      map.current = null;
    };
  }, []);

  // the latest props, for camera moves that start outside the draw effect (a search closing)
  const latest = useRef({ plan, origin, destination, padLeft });
  latest.current = { plan, origin, destination, padLeft };

  /** Frame the trip, leaving room for the floating panel: the route, or A and B, or the one
   *  place picked so far (zoomed in, like a maps app). `home`: with nothing picked, go back
   *  to the Singapore overview (a search closed without a pick). */
  const fitView = (home = false) => {
    const m = map.current;
    if (!m) return;
    const { plan, origin, destination, padLeft } = latest.current;
    const duration = reducedMotion() ? 0 : 1100;
    const pts: LngLat[] = [];
    if (plan) pts.push(...plan.route.geometry);
    if (origin) pts.push([origin.lng, origin.lat]);
    if (destination) pts.push([destination.lng, destination.lat]);
    const padding = { top: 70, bottom: 60, left: padLeft + 50, right: 70 };
    // single points use `offset`, never `padding`: padding on flyTo/easeTo sticks to the map,
    // and the next fitBounds adds its own on top — the route then fits into a ~40 px strip
    const offset: [number, number] = [(padding.left - padding.right) / 2, (padding.top - padding.bottom) / 2];
    if (pts.length >= 2) {
      let [minX, minY, maxX, maxY] = [180, 90, -180, -90];
      for (const [x, y] of pts) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
      m.fitBounds(
        [
          [minX, minY],
          [maxX, maxY],
        ],
        { padding, maxZoom: 15, duration },
      );
    } else if (pts.length === 1) {
      m.flyTo({ center: pts[0], zoom: 15, offset, duration });
    } else if (home) {
      m.flyTo({ center: SG_CENTER, zoom: 10.6, offset: [padLeft / 2, 0], duration });
    }
  };

  // route + main markers
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      markers.current.forEach((mk) => mk.remove());
      markers.current = [];
      if (anim.current) cancelAnimationFrame(anim.current);
      const src = m.getSource("route") as GeoJSONSource | undefined;
      const player = m.getSource("player") as GeoJSONSource | undefined;
      player?.setData(pointFC(null));
      const features: Feature[] = [];
      if (plan) {
        const legs = plan.route.legs.length
          ? plan.route.legs.map((l) => ({ mode: l.mode.toUpperCase(), coords: l.geometry }))
          : [{ mode: plan.route.mode.toUpperCase(), coords: plan.route.geometry }];
        for (const l of legs) {
          features.push({
            type: "Feature",
            properties: { mode: l.mode, color: LEG_COLORS[l.mode] ?? ROUTE_COLOR },
            geometry: { type: "LineString", coordinates: l.coords },
          });
        }
      }
      // a glowing "player" runs the route from A to B, drawing it as it goes
      const { parts, total } = prepare(features);
      if (!total || reducedMotion()) {
        src?.setData({ type: "FeatureCollection", features });
      } else {
        const start = performance.now();
        const step = (now: number) => {
          const t = Math.min(1, (now - start) / DRAW_MS);
          const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          const { features: drawn, head } = cut(parts, eased * total);
          src?.setData({ type: "FeatureCollection", features: drawn });
          player?.setData(pointFC(t < 1 ? head : null));
          if (t < 1) anim.current = requestAnimationFrame(step);
        };
        anim.current = requestAnimationFrame(step);
      }

      let order = 0;
      const add = (lng: number, lat: number, node: HTMLElement, onClick?: () => void) => {
        node.style.animationDelay = `${300 + order++ * 120}ms`;
        if (onClick) node.addEventListener("click", (e) => (e.stopPropagation(), onClick()));
        // MapLibre positions the wrapper; animating the inner node keeps the anchor stable
        const wrap = document.createElement("div");
        wrap.appendChild(node);
        markers.current.push(new maplibregl.Marker({ element: wrap }).setLngLat([lng, lat]).addTo(m));
      };
      if (origin) add(origin.lng, origin.lat, el("pin pin-origin", "A", origin.name ?? "Start"));
      if (destination) add(destination.lng, destination.lat, el("pin pin-dest", "🏁", destination.name ?? "Finish"));
      if (plan) {
        const seen = new Set<string>();
        plan.stops.forEach((sp, i) => {
          const c = sp.chosen;
          if (!c) return;
          const node = el(
            `pin-stop${seen.has(c.osm_id) ? " pin-offset" : ""}`,
            `<span class="hex">${i + 1}</span>`,
            `${sp.request.label}: ${c.name ?? "Unnamed"}`,
          );
          node.dataset.stop = sp.request.id;
          seen.add(c.osm_id);
          add(c.lng, c.lat, node, () => onSelectStop(sp.request.id));
        });
      }
      fitView();
    };
    if (ready.current) draw();
    else pending.current = draw;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, origin, destination, padLeft]);

  // Typing a Start / Finish, like a maps app's search box: every suggestion is a dot, the
  // highlighted one a big A / 🏁 pin with its name, and the camera flies to it — zooming out
  // and back in for far jumps. When the list closes the map frames the trip again (a pick
  // also redraws above; both land on the same view).
  const previewMarkers = useRef<maplibregl.Marker[]>([]);
  const previewNodes = useRef<HTMLElement[]>([]);
  const previewing = useRef(false);
  const camTimer = useRef<number | undefined>(undefined);
  const pResults = preview?.results;
  const pKind = preview?.kind;
  const pActive = preview?.active ?? 0;

  // markers: rebuilt only when the suggestions change, so moving the highlight doesn't re-pop them
  useEffect(() => {
    const m = map.current;
    previewMarkers.current.forEach((mk) => mk.remove());
    previewMarkers.current = [];
    previewNodes.current = [];
    if (!m) return;
    if (!pResults?.length || !pKind) {
      window.clearTimeout(camTimer.current);
      if (previewing.current) {
        previewing.current = false;
        fitView(true);
      }
      return;
    }
    previewing.current = true;
    for (const r of pResults) {
      const node = el(
        `preview-pin preview-${pKind}`,
        `<span class="preview-glyph">${pKind === "origin" ? "A" : "🏁"}</span><span class="preview-label">${esc(r.name)}</span>`,
        r.name,
      );
      const wrap = document.createElement("div");
      wrap.appendChild(node);
      previewNodes.current.push(node);
      previewMarkers.current.push(new maplibregl.Marker({ element: wrap }).setLngLat([r.lng, r.lat]).addTo(m));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pResults, pKind]);

  // highlight + camera follow the highlighted suggestion
  useEffect(() => {
    const m = map.current;
    if (!m || !pResults?.length) return;
    const i = Math.min(pActive, pResults.length - 1);
    previewNodes.current.forEach((n, k) => {
      n.classList.toggle("preview-active", k === i);
      if (n.parentElement) n.parentElement.style.zIndex = k === i ? "3" : "1";
    });
    const r = pResults[i];
    window.clearTimeout(camTimer.current);
    // a short pause, so skimming the list with the mouse doesn't send the camera everywhere
    camTimer.current = window.setTimeout(() => {
      m.flyTo({
        center: [r.lng, r.lat],
        zoom: 15,
        offset: [latest.current.padLeft / 2, 0],
        ...(reducedMotion() ? { duration: 0 } : { speed: 1.6, maxDuration: 1600 }),
      });
    }, 140);
    // a pending move must not land after the list closed (it would undo the re-frame)
    return () => window.clearTimeout(camTimer.current);
  }, [pResults, pActive]);

  // prayer-time markers: the plan only has them when the trip asked for a mosque or surau
  useEffect(() => {
    const m = map.current;
    prayerMarkers.current.forEach((mk) => mk.remove());
    prayerMarkers.current = [];
    if (!m || !plan) return;
    plan.prayer_times.forEach((p, i) => {
      if (!p.position || p.note) return;
      const node = el("prayer-pin", "🕌", `${PRAYER_LABEL[p.name] ?? p.name} begins ${fmtTime(p.time)} — you'll be about here`);
      node.style.animationDelay = `${400 + i * 120}ms`;
      const wrap = document.createElement("div");
      wrap.appendChild(node);
      prayerMarkers.current.push(new maplibregl.Marker({ element: wrap }).setLngLat([p.position.lng, p.position.lat]).addTo(m));
    });
  }, [plan]);

  // selected stop: highlight + show alternatives
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    candMarkers.current.forEach((mk) => mk.remove());
    candMarkers.current = [];
    document.querySelectorAll<HTMLElement>(".pin-stop").forEach((n) =>
      n.classList.toggle("pin-selected", n.dataset.stop === selectedStopId),
    );
    if (!plan || !selectedStopId) return;
    const sp = plan.stops.find((s) => s.request.id === selectedStopId);
    if (!sp) return;
    sp.candidates.forEach((c, i) => {
      if (sp.chosen && c.osm_id === sp.chosen.osm_id) return;
      const node = el("cand-pin", String(i + 1), `${c.name ?? "Unnamed"} · +${Math.round(addedMin(c))} min`);
      node.style.animationDelay = `${i * 70}ms`;
      const popup = new maplibregl.Popup({ offset: 14, closeButton: false }).setHTML(
        `<div style="font:600 13px 'Plus Jakarta Sans',sans-serif;color:#fff">${esc(c.name ?? "Unnamed place")}</div>` +
          `<div style="font:12px 'Plus Jakarta Sans',sans-serif;color:#94a3b8">+${Math.round(addedMin(c))} min · ETA ${fmtTime(c.eta)}</div>`,
      );
      node.addEventListener("dblclick", () => onPickCandidate?.(sp.request.id, c.osm_id));
      const wrap = document.createElement("div");
      wrap.appendChild(node);
      candMarkers.current.push(new maplibregl.Marker({ element: wrap }).setLngLat([c.lng, c.lat]).setPopup(popup).addTo(m));
    });
    // offset, not padding (see the fit above)
    if (sp.chosen) m.easeTo({ center: [sp.chosen.lng, sp.chosen.lat], offset: [padLeft / 2, 0], duration: 700 });
  }, [plan, selectedStopId, onPickCandidate, padLeft]);

  return <div ref={box} className="h-full w-full" role="region" aria-label="Map" />;
}
