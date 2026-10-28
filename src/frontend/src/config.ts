import type { Config, ConfigOverrides } from "./types";

/** Client-side mirror of the backend layering, used to show inherited values in editors. */
export function mergeConfig(defaults: Config, ...layers: (ConfigOverrides | undefined | null)[]): Config {
  const out: Config = JSON.parse(JSON.stringify(defaults));
  for (const layer of layers) {
    for (const [mod, vals] of Object.entries(layer ?? {})) {
      if (!out[mod]) continue;
      Object.assign(out[mod], vals);
    }
  }
  return out;
}

export function countOverrides(cfg: ConfigOverrides | undefined): number {
  return Object.values(cfg ?? {}).reduce((n, m) => n + Object.keys(m).length, 0);
}

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function fmtDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

export function timeAgo(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return fmtDate(iso);
}
