import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import Landing from "./pages/Landing";
import { usePath } from "./lib/router";
import "./index.css";

registerSW({ immediate: true });

// the planner pulls in MapLibre (~800 kB) — the landing page shouldn't wait for it
const Planner = lazy(() => import("./pages/Planner"));

function Loading() {
  return (
    <div className="flex h-dvh items-center justify-center bg-ink-950">
      <div className="text-center">
        <div className="hex mx-auto mb-4 flex h-14 w-16 animate-bob items-center justify-center bg-gradient-to-br from-brand-300 to-brand-600 font-logo text-xl text-ink-950">
          SQ
        </div>
        <p className="font-display text-sm uppercase tracking-[0.3em] text-slate-400">
          Loading<span className="animate-blink">…</span>
        </p>
      </div>
    </div>
  );
}

function Root() {
  const path = usePath();
  if (path.startsWith("/plan")) {
    return (
      <Suspense fallback={<Loading />}>
        <Planner />
      </Suspense>
    );
  }
  return <Landing />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
