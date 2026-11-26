import { useEffect, useState, type MouseEvent } from "react";

/** Tiny pathname router: "/" is the landing page, "/plan" the planner.
 * Hosting must serve index.html for unknown paths (vercel.json does; Vite dev does). */
const EVENT = "app:navigate";

export function navigate(to: string) {
  if (to === location.pathname + location.hash) return;
  history.pushState(null, "", to);
  window.dispatchEvent(new Event(EVENT));
  if (!to.includes("#")) window.scrollTo({ top: 0 });
}

export function usePath(): string {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const on = () => setPath(location.pathname);
    window.addEventListener("popstate", on);
    window.addEventListener(EVENT, on);
    return () => {
      window.removeEventListener("popstate", on);
      window.removeEventListener(EVENT, on);
    };
  }, []);
  return path;
}

/** onClick for <a href> that navigates in-app but keeps ctrl/⌘-click opening a new tab. */
export function linkTo(to: string) {
  return (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(to);
  };
}
