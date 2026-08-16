import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const KEY = "mm.theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function apply(theme: Theme): void {
  const dark = theme === "system" ? systemPrefersDark() : theme === "dark";
  document.documentElement.classList.toggle("dark", dark);
}

function read(): Theme {
  const saved = localStorage.getItem(KEY);
  return saved === "light" || saved === "dark" ? saved : "system";
}

/**
 * Light/dark/system theme, persisted.
 *
 * The inline script in index.html applies the same resolution before first
 * paint; this hook keeps it in sync afterwards. "system" deliberately stores
 * nothing, so the app keeps following the OS if that preference changes.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() =>
    typeof window === "undefined" ? "system" : read()
  );

  useEffect(() => {
    apply(theme);
  }, [theme]);

  // Follow the OS while on "system".
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    if (next === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, next);
    setThemeState(next);
  }, []);

  return { theme, setTheme };
}
