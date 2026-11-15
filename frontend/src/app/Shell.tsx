import { useCallback, useEffect } from "react";
import { Outlet, useSearchParams } from "react-router";

import { SettingsOverlay } from "../preferences/SettingsOverlay";
import { Rail } from "./rail/Rail";
import { RailProvider } from "./rail/RailContext";
import { painted, useTheme } from "./useTheme";

/** The frame every page sits in: the one rail (#511) beside the page. Settings is an overlay over
 *  the page you are on (`?settings=<section>`). */
export function Shell() {
  const [theme] = useTheme();
  useEffect(() => {
    document.documentElement.dataset.theme = painted(theme);
  }, [theme]);


  // **Settings is an overlay over the page you are on**, opened by `?settings=<section>` (the
  // overlay's design, 2026-10-01). The address carries it, so it can be linked, and closing it
  // removes only that parameter: the page and its own state stay as they were.
  const [params, setParams] = useSearchParams();
  const settings = params.get("settings");
  const withSettings = (section: string | null) => {
    const next = new URLSearchParams(params);
    if (section === null) next.delete("settings");
    else next.set("settings", section);
    return next;
  };
  const openSection = (section: string) => setParams(withSettings(section), { replace: true });
  const closeSettings = useCallback(() => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("settings");
      return next;
    });
  }, [setParams]);

  return (
    <RailProvider>
      <div className="flex h-dvh bg-paper">
        <Rail />
        <main className="flex-1 min-w-0 h-dvh grid grid-rows-[minmax(0,1fr)] overflow-hidden">
          <Outlet />
        </main>
      </div>
      {settings !== null && (
        <SettingsOverlay section={settings} onSelect={openSection} onClose={closeSettings} />
      )}
    </RailProvider>
  );
}
