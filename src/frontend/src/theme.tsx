import { createContext, useContext, useLayoutEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "writing-tutor-theme";

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : systemTheme();
}

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme((value) => value === "dark" ? "light" : "dark") }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}

export function ThemeToggle({ className = "btn outline" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" className={className} onClick={toggleTheme} title={`Use ${nextTheme} mode`} aria-label={`Use ${nextTheme} mode`}>
      <span className="ico" aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
      <span className="label">{nextTheme[0].toUpperCase() + nextTheme.slice(1)} mode</span>
    </button>
  );
}

export function ThemeSwitch() {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";
  return (
    <div className="theme-switch">
      <span aria-hidden="true">☾</span>
      <span>Dark mode</span>
      <button
        type="button"
        className={`switch ${dark ? "on" : ""}`}
        role="switch"
        aria-checked={dark}
        aria-label="Dark mode"
        onClick={toggleTheme}
      />
    </div>
  );
}
