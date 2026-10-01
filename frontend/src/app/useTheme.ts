import { storageName, useBrowserSetting } from "../preferences/useBrowserSetting";

export type Theme = "system" | "light" | "dark";

/** The old toggle stored `light` or `dark` under `comeni-theme`; a choice made with it is kept.
 *
 * **Moved, not only read**, so the menu's row (which reads the new name) and the shell agree. */
function legacy(): Theme | null {
  try {
    const old = localStorage.getItem("comeni-theme");
    if (old !== "light" && old !== "dark") return null;
    if (localStorage.getItem(storageName("appearance.theme")) === null) {
      localStorage.setItem(storageName("appearance.theme"), old);
    }
    localStorage.removeItem("comeni-theme");
    return old;
  } catch {
    return null;
  }
}

export function painted(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [raw, set] = useBrowserSetting("appearance.theme", legacy() ?? "system");
  const theme: Theme = raw === "light" || raw === "dark" ? raw : "system";
  return [theme, set];
}
