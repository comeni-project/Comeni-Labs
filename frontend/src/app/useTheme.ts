import { useBrowserSetting } from "../preferences/useBrowserSetting";

export type Theme = "system" | "light" | "dark";

/** The old toggle's key is dropped, never read (review I-1).
 *
 * **Not migrated**: the old shell wrote `comeni-theme` on every mount, including a value it had
 * only worked out from the OS, so a stored value is not evidence that anybody chose it. Treating
 * it as a choice would fix nearly every past visitor to light or dark. The cost is the few who
 * did press the toggle, who press *Dark* once more in Settings → Appearance. */
let forgotten = false;
function forgetOldToggle(): void {
  if (forgotten) return;
  forgotten = true;
  try {
    localStorage.removeItem("comeni-theme");
  } catch {
    // a browser that refuses storage has nothing to forget
  }
}

export function painted(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  forgetOldToggle();
  const [raw, set] = useBrowserSetting("appearance.theme", "system");
  const theme: Theme = raw === "light" || raw === "dark" ? raw : "system";
  return [theme, set];
}
