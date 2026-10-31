import { useCallback, useEffect } from "react";
import { Link, NavLink, Outlet, useLocation, useSearchParams } from "react-router";

import { SettingsOverlay } from "../preferences/SettingsOverlay";
import { Jump } from "./Jump";
import { painted, useTheme } from "./useTheme";


/** Where the `?` goes. One constant, so the address changes in one place when a docs site is
 *  published; until then the index in the public repository. */
export const DOCS_URL = "https://github.com/comeni-project/Comeni-Labs/blob/main/docs/index.md";

/** A section of the product. The one you are in is a raised pill; the others are plain text. */
function Tab({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-[6px] rounded-control border no-underline transition-colors ${
          isActive
            ? "bg-surface border-line text-ink font-semibold"
            : "border-transparent text-ink-2 hover:text-ink"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

/** The product's mark: three stations on a line, as on Comeni Code's routes. */
function Mark() {
  return (
    <svg width="30" height="16" viewBox="0 0 30 16" aria-hidden="true" className="shrink-0">
      <line x1="3" y1="8" x2="27" y2="8" stroke="var(--done)" strokeWidth="4" strokeLinecap="round" />
      {[4, 15, 26].map((cx) => (
        <circle key={cx} cx={cx} cy="8" r="3.5" fill="var(--surface)" stroke="var(--ink)" strokeWidth="2" />
      ))}
    </svg>
  );
}

const round = "w-8 h-8 shrink-0 rounded-full border border-line-2 flex items-center justify-center " +
  "text-ink-2 hover:text-ink no-underline transition-colors";

/** The frame every page sits in: the mark going home, the three sections, then jump, help and
 *  settings. Settings is an overlay over the page you are on (`?settings=<section>`). */
export function Shell() {
  const [theme] = useTheme();
  useEffect(() => {
    document.documentElement.dataset.theme = painted(theme);
  }, [theme]);


  // **Settings is an overlay over the page you are on**, opened by `?settings=<section>` (the
  // overlay's design, 2026-10-01). The address carries it, so it can be linked, and closing it
  // removes only that parameter: the page and its own state stay as they were.
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const settings = params.get("settings");
  const withSettings = (section: string | null) => {
    const next = new URLSearchParams(params);
    if (section === null) next.delete("settings");
    else next.set("settings", section);
    return next;
  };
  const gear = `${location.pathname}?${withSettings("").toString()}`;
  const openSection = (section: string) => setParams(withSettings(section), { replace: true });
  const closeSettings = useCallback(() => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("settings");
      return next;
    });
  }, [setParams]);

  return (
    <div className="grid grid-rows-[auto_1fr] h-dvh">
      <header className="border-b border-line bg-paper">
        <div className={`gutter min-h-[60px] py-[10px] flex flex-wrap items-center gap-x-[26px] gap-y-2 ${
          location.pathname.startsWith("/registry") ? "frame" : ""}`}>
        <Link to="/" aria-label="Comeni — home" className="flex items-center gap-[10px] text-ink no-underline">
          <Mark />
          <span className="text-brand font-bold tracking-[-.01em]">Comeni Labs</span>
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1">
          <Tab to="/build">Build</Tab>
          <Tab to="/runs">Runs</Tab>
          <Tab to="/registry">Registry</Tab>
        </nav>
        <div className="ml-auto flex items-center gap-[10px]">
          <Jump />
          <a href={DOCS_URL} target="_blank" rel="noreferrer" aria-label="Help" title="Help"
             className={`${round} font-semibold`}>?</a>
          <Link to={gear} aria-label="Settings" title="Settings" className={round}>
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none"
                 stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" />
            </svg>
          </Link>
        </div>
        </div>
      </header>
      <Outlet />
      {settings !== null && (
        <SettingsOverlay section={settings} onSelect={openSection} onClose={closeSettings} />
      )}
    </div>
  );
}
