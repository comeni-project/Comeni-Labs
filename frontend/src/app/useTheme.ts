import { useBrowserSetting } from "../preferences/useBrowserSetting";

export type Theme = "system" | "light" | "dark";

/** The theme a choice paints. **Light first:** *system* is light unless the system asks for dark,
 *  so a browser that reports no preference gets the palette the boards are drawn in. */
export function painted(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [raw, set] = useBrowserSetting("appearance.theme", "system");
  const theme: Theme = raw === "light" || raw === "dark" ? raw : "system";
  return [theme, set];
}
