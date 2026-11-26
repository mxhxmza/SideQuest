import type { Category, Cuisine, GeocodeResult, Health, ParseResponse, TripPlan, TripRequest } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 90_000);
  try {
    const r = await fetch(BASE + path, {
      ...init,
      signal: init?.signal ?? ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!r.ok) {
      let msg = `${r.status} ${r.statusText}`;
      try {
        const j = await r.json();
        if (j?.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch {
        /* not JSON */
      }
      throw new ApiError(r.status, msg);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  health: (timeoutMs = 75_000) => req<Health>("/api/health", { timeoutMs }),
  categories: () => req<Category[]>("/api/categories"),
  cuisines: () => req<Cuisine[]>("/api/cuisines"),
  geocode: (q: string, signal?: AbortSignal) =>
    req<GeocodeResult[]>(`/api/geocode?q=${encodeURIComponent(q)}`, { signal }),
  parse: (text: string, departure_time?: string, signal?: AbortSignal) =>
    req<ParseResponse>("/api/parse", {
      method: "POST",
      body: JSON.stringify({ text, departure_time }),
      signal,
    }),
  plan: (trip: TripRequest) =>
    req<TripPlan>("/api/plan", { method: "POST", body: JSON.stringify(trip), timeoutMs: 120_000 }),
};
