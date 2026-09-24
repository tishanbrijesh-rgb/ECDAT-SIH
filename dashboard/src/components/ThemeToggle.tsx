// Theme toggle — cycles light / dark / system.
// Persists choice to localStorage and applies data-theme to <html>.
import { useState, useEffect } from "react";

const STORAGE_KEY = "ecdat-theme";
type Theme = "light" | "dark" | "system";

function applyTheme(theme: Theme): string {
  const resolved =
    theme === "system"
      ? matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  document.documentElement.setAttribute("data-theme", resolved);
  return resolved;
}

function getInitialTheme(): { stored: Theme; resolved: string } {
  try {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme) || "system";
    return { stored, resolved: applyTheme(stored) };
  } catch {
    return { stored: "system" as Theme, resolved: applyTheme("system") };
  }
}

const { stored: initialStored, resolved: initialResolved } = getInitialTheme();

interface Props {
  className?: string;
}

export default function ThemeToggle({ className }: Props) {
  const [theme, setTheme] = useState<Theme>(initialStored);
  const [resolved, setResolved] = useState(initialResolved);

  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (theme === "system") setResolved(applyTheme("system"));
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const cycle = () => {
    const next: Theme = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    const r = applyTheme(next);
    setTheme(next);
    setResolved(r);
  };

  const label = resolved === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      className={`theme-toggle ${className ?? ""}`}
      onClick={cycle}
      aria-label={label}
      title={label}
      type="button"
    >
      {/* Sun icon */}
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        style={{ display: resolved === "light" ? "block" : "none" }}
      >
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>
      {/* Moon icon */}
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        style={{ display: resolved === "dark" ? "block" : "none" }}
      >
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
      {/* System icon (laptop) */}
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        style={{ display: theme === "system" ? "block" : "none" }}
      >
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    </button>
  );
}
