import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Point, TripPlan } from "../types";
import { addedMin, fmtTime, PRAYER_LABEL } from "../lib/format";

const STYLE = "https://tiles.openfreemap.org/styles/liberty";
const SG_CENTER: [number, number] = [103.8198, 1.3521];
const LEG_COLORS: Record<string, string> = {
  WALK: "#64748b",
  BUS: "#16a34a",
  SUBWAY: "#7c3aed",
  RAIL: "#7c3aed",
  TRAM: "#0891b2",
};
const ROUTE_COLOR = "#0a9b80";

interface Props {
  plan: TripPlan | null;
  origin: Point | null;
  destination: Point | null;
  selectedStopId: string | null;
  onSelectStop: (id: string) => void;
  onPickCandidate?: (stopId: string, osmId: string) => void;
  /** px of map covered by the floating panel on the left (desktop) */
  padLeft?: number;
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

export default function MapView({ plan, origin, destination, selectedStopId, onSelectStop, onPickCandidate, padLeft = 0 }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const candMarkers = useRef<maplibregl.Marker[]>([]);
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
      m.addSource("route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "route-glow",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 16, "line-opacity": 0.18, "line-blur": 6 },
      });
      m.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#ffffff", "line-width": 9 },
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

  // route + main markers
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      markers.current.forEach((mk) => mk.remove());
      markers.current = [];
      if (anim.current) cancelAnimationFrame(anim.current);
      const src = m.getSource("route") as GeoJSONSource | undefined;
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
      // draw the route on progressively (≈1.3 s)
      const total = features.reduce((n, f) => n + f.geometry.coordinates.length, 0);
      const frame = (k: number) => ({
        type: "FeatureCollection" as const,
        features: features
          .map((f, i) => {
            const before = features.slice(0, i).reduce((n, g) => n + g.geometry.coordinates.length, 0);
            const take = Math.max(0, Math.min(f.geometry.coordinates.length, k - before));
            return { ...f, geometry: { ...f.geometry, coordinates: f.geometry.coordinates.slice(0, take) } };
          })
          .filter((f) => f.geometry.coordinates.length >= 2),
      });
      if (!total || reducedMotion()) {
        src?.setData({ type: "FeatureCollection", features });
      } else {
        const start = performance.now();
        const step = (now: number) => {
          const t = Math.min(1, (now - start) / 1300);
          const eased = 1 - Math.pow(1 - t, 3);
          src?.setData(frame(Math.ceil(eased * total)));
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
      if (destination) add(destination.lng, destination.lat, el("pin pin-dest", "B", destination.name ?? "End"));
      if (plan) {
        plan.prayer_times.forEach((p) => {
          if (!p.position || p.note) return;
          add(
            p.position.lng,
            p.position.lat,
            el("prayer-pin", "🕌", `${PRAYER_LABEL[p.name] ?? p.name} begins ${fmtTime(p.time)} — you'll be about here`),
          );
        });
        const seen = new Set<string>();
        plan.stops.forEach((sp, i) => {
          const c = sp.chosen;
          if (!c) return;
          const node = el(
            `pin pin-stop${seen.has(c.osm_id) ? " pin-offset" : ""}`,
            String(i + 1),
            `${sp.request.label}: ${c.name ?? "Unnamed"}`,
          );
          node.dataset.stop = sp.request.id;
          seen.add(c.osm_id);
          add(c.lng, c.lat, node, () => onSelectStop(sp.request.id));
        });
      }
      // fit, leaving room for the floating panel
      const pts: [number, number][] = [];
      if (plan) pts.push(...plan.route.geometry);
      if (origin) pts.push([origin.lng, origin.lat]);
      if (destination) pts.push([destination.lng, destination.lat]);
      const padding = { top: 70, bottom: 60, left: padLeft + 50, right: 70 };
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
          { padding, maxZoom: 15, duration: reducedMotion() ? 0 : 1100 },
        );
      } else if (pts.length === 1) {
        m.flyTo({ center: pts[0], zoom: 13, padding, duration: reducedMotion() ? 0 : 1100 });
      }
    };
    if (ready.current) draw();
    else pending.current = draw;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, origin, destination, padLeft]);

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
        `<div style="font:600 13px 'Plus Jakarta Sans',sans-serif">${esc(c.name ?? "Unnamed place")}</div>` +
          `<div style="font:12px 'Plus Jakarta Sans',sans-serif;color:#475569">+${Math.round(addedMin(c))} min · ETA ${fmtTime(c.eta)}</div>`,
      );
      node.addEventListener("dblclick", () => onPickCandidate?.(sp.request.id, c.osm_id));
      const wrap = document.createElement("div");
      wrap.appendChild(node);
      candMarkers.current.push(new maplibregl.Marker({ element: wrap }).setLngLat([c.lng, c.lat]).setPopup(popup).addTo(m));
    });
    if (sp.chosen) m.easeTo({ center: [sp.chosen.lng, sp.chosen.lat], padding: { left: padLeft, top: 0, right: 0, bottom: 0 }, duration: 700 });
  }, [plan, selectedStopId, onPickCandidate, padLeft]);

  return <div ref={box} className="h-full w-full" role="region" aria-label="Map" />;
}
