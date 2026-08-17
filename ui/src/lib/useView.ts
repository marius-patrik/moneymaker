import { useCallback, useEffect, useState } from "react";

export type View = "trade" | "portfolio" | "history" | "research" | "settings";

const KEY = "mm.view";
const EVENT = "mm:view";

export const VIEWS: View[] = ["trade", "portfolio", "history", "research", "settings"];

function isView(v: string | null): v is View {
  return !!v && (VIEWS as string[]).includes(v);
}

/**
 * Which screen is showing.
 *
 * State rather than routing: this is one process on one machine with no
 * links to share and no server rendering, so a router only added a URL
 * nobody reads and a history stack that fought the back button on mobile.
 * The view survives a reload because it is persisted, which is the only
 * thing the URL was really buying.
 */
export function useView() {
  const [view, setState] = useState<View>(() => {
    const saved = localStorage.getItem(KEY);
    return isView(saved) ? saved : "trade";
  });

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<View>).detail;
      if (isView(detail)) setState(detail);
    };
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);

  const setView = useCallback((next: View) => {
    localStorage.setItem(KEY, next);
    setState(next);
    window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
  }, []);

  return { view, setView };
}

/** The API returns route-ish strings; this is the one place they become views. */
export function viewFromRoute(route: string): View {
  const cleaned = route.replace(/^\//, "") as View;
  return isView(cleaned) ? cleaned : "trade";
}

/** Navigate from anywhere without threading a callback through the tree. */
export function goTo(view: View) {
  localStorage.setItem(KEY, view);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: view }));
}
