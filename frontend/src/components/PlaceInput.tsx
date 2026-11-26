import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { GeocodeResult, Point } from "../types";

interface Props {
  label: string;
  value: Point | null;
  onChange: (p: Point | null) => void;
  /** current text in the box, so the form can resolve a typed-but-unpicked place */
  onText?: (text: string) => void;
  placeholder?: string;
  allowLocate?: boolean;
  /** coloured A/B marker inside the field; label becomes screen-reader only */
  dot?: "origin" | "dest";
}

export default function PlaceInput({ label, value, onChange, onText, placeholder, allowLocate, dot }: Props) {
  const [text, setText] = useState(value?.name ?? "");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const typed = useRef(false);
  // Enter pressed before suggestions arrived: take the top one when they do
  const pickWhenReady = useRef(false);

  // a place chosen elsewhere (suggestion, location button, resolved on submit) shows its name
  useEffect(() => {
    if (value) {
      typed.current = false;
      setText(value.name ?? "");
      onText?.(value.name ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const pick = (r: GeocodeResult) => {
    typed.current = false;
    pickWhenReady.current = false;
    setText(r.name);
    setOpen(false);
    setErr(null);
    onChange({ lat: r.lat, lng: r.lng, name: r.name });
  };

  useEffect(() => {
    if (!typed.current) return;
    const q = text.trim();
    if (q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api.geocode(q, ctrl.signal);
        setResults(r);
        setActive(0);
        setErr(r.length ? null : `No places found for “${q}”`);
        if (pickWhenReady.current && r.length) pick(r[0]);
        else setOpen(r.length > 0);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setErr("Search failed — is the server running?");
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const locate = () => {
    if (!navigator.geolocation) return setErr("Location not available");
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(false);
        onChange({ lat: pos.coords.latitude, lng: pos.coords.longitude, name: "Current location" });
      },
      () => {
        setBusy(false);
        setErr("Couldn't get your location");
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  const id = `place-${label.toLowerCase()}`;
  return (
    <div className="relative">
      <label htmlFor={id} className={dot ? "sr-only" : "lbl"}>
        {label}
      </label>
      <div className="relative flex gap-2">
        {dot && (
          <span
            aria-hidden
            className={`pointer-events-none absolute left-3 top-1/2 z-10 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-[9px] font-extrabold text-white shadow ${
              dot === "origin" ? "bg-emerald-500" : "bg-rose-500"
            }`}
          >
            {dot === "origin" ? "A" : "B"}
          </span>
        )}
        {value && (
          <span
            aria-label="Place selected"
            className={`pointer-events-none absolute top-1/2 z-10 -translate-y-1/2 animate-pop text-sm text-emerald-500 ${allowLocate ? "right-14" : "right-3"}`}
          >
            ✓
          </span>
        )}
        <input
          id={id}
          className={`input flex-1 ${dot ? "pl-10" : ""} ${value ? "pr-8" : ""}`}
          value={text}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          onChange={(e) => {
            typed.current = true;
            pickWhenReady.current = false;
            setText(e.target.value);
            onText?.(e.target.value);
            if (value) onChange(null);
          }}
          onFocus={() => results.length && typed.current && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "Escape") return setOpen(false);
            if (open && results.length) {
              if (e.key === "ArrowDown") (e.preventDefault(), setActive((a) => Math.min(a + 1, results.length - 1)));
              if (e.key === "ArrowUp") (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
              if (e.key === "Enter") (e.preventDefault(), pick(results[active]));
              return;
            }
            // Enter on a typed-but-unpicked place must not submit the form
            if (e.key === "Enter" && !value && text.trim().length >= 2) {
              e.preventDefault();
              if (results.length && !busy) pick(results[0]);
              else pickWhenReady.current = true;
            }
          }}
        />
        {allowLocate && (
          <button type="button" className="btn-ghost px-3 text-base" onClick={locate} title="Use my location" aria-label="Use my location">
            📍
          </button>
        )}
      </div>
      {busy && !value && (
        <span className={`pointer-events-none absolute top-1/2 -translate-y-1/2 ${allowLocate ? "right-14" : "right-3"}`}>
          <span className="block h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500" />
        </span>
      )}
      {err && <p className="mt-1 animate-fade-up text-xs text-rose-600">{err}</p>}
      {open && results.length > 0 && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute z-30 mt-1.5 max-h-72 w-full animate-slide-down overflow-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-xl"
        >
          {results.map((r, i) => (
            <li
              key={`${r.lat},${r.lng},${i}`}
              role="option"
              aria-selected={i === active}
              className={`cursor-pointer rounded-xl px-3 py-2 text-sm transition ${i === active ? "bg-brand-50" : ""}`}
              onMouseDown={(e) => (e.preventDefault(), pick(r))}
              onMouseEnter={() => setActive(i)}
            >
              <div className="font-medium text-slate-800">{r.name}</div>
              {r.address && <div className="truncate text-xs text-slate-500">{r.address}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
