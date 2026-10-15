import { useSyncExternalStore } from "react";

/** A setting kept by this browser rather than the server — the theme is one (spec §7).
 *
 * **Shared through one event**, so the menu and the shell agree the moment either changes it;
 * the `storage` event covers another tab. **A browser that refuses storage** (a private window)
 * still gets the value for this session: `memory` holds what could not be written.
 */
const EVENT = "comeni-browser-setting";
const memory = new Map<string, string>();

export function storageName(key: string): string {
  return `comeni.${key}`;
}

function read(name: string): string | null {
  try {
    return localStorage.getItem(name);
  } catch {
    return memory.get(name) ?? null;
  }
}

function subscribe(changed: () => void): () => void {
  window.addEventListener(EVENT, changed);
  window.addEventListener("storage", changed);
  return () => {
    window.removeEventListener(EVENT, changed);
    window.removeEventListener("storage", changed);
  };
}

export function useBrowserSetting(key: string, fallback: string): [string, (value: string) => void] {
  const name = storageName(key);
  const value = useSyncExternalStore(subscribe, () => read(name) ?? fallback);
  const set = (next: string) => {
    try {
      localStorage.setItem(name, next);
    } catch {
      memory.set(name, next); // only when storage refuses: kept for this session
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return [value, set];
}
