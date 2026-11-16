import { Link, NavLink, useLocation, useSearchParams } from "react-router";

import { DOCS_URL } from "../address";
import { Jump } from "../Jump";
import { painted, useTheme } from "../useTheme";
import { Icon, type IconName } from "./icons";
import { useRail } from "./RailContext";

/** The one rail every page sits beside (#511, "The rail's grammar"):
 *
 * 1. **Places**, always on top and never changing: Home · Forge · Registry.
 * 2. **What is open**, one fixed slot a page fills with `<RailSlot>`; empty, it is the dashed
 *    "Open an analysis…", so the slot never disappears.
 * 3. **This page's controls**, below a divider and labelled, from `<RailControls>`.
 * 4. **The bottom**, always the same: Settings · light/dark · help · Local.
 *
 * It collapses to icons; on a phone it starts collapsed and opens over the page. */
export function Rail() {
  const rail = useRail();
  const { mini } = rail;
  const [theme, setTheme] = useTheme();
  const dark = painted(theme) === "dark";

  // Settings is an overlay over the page you are on (`?settings=<section>`), so its link keeps
  // the page and only adds the parameter.
  const location = useLocation();
  const [params] = useSearchParams();
  const gear = new URLSearchParams(params);
  gear.set("settings", "");
  const settings = `${location.pathname}?${gear.toString()}`;

  if (rail.hidden > 0) return null;

  const toggle = (
    <button type="button" onClick={() => rail.setMini(!mini)}
            aria-label={mini ? "Expand sidebar" : "Collapse sidebar"}
            title={mini ? "Expand sidebar" : "Collapse sidebar"}
            className="w-11 h-11 sm:w-9 sm:h-9 shrink-0 rounded-control flex items-center justify-center border-0 bg-transparent
                       text-ink-2 hover:bg-surface-2 hover:text-ink cursor-pointer">
      <Icon name="sidebar" />
    </button>
  );

  return (
    <>
    {/* On a phone the open rail lies over the page; the icon rail keeps its place under it. */}
    {rail.overlay && <div className="w-[60px] shrink-0" aria-hidden="true" />}
    {rail.overlay && (
      <div className="fixed inset-0 z-30 bg-[var(--scrim)]" aria-hidden="true" onClick={() => rail.setMini(true)} />
    )}
    <nav aria-label="Comeni"
         className={`flex flex-col shrink-0 h-dvh overflow-y-auto overflow-x-hidden bg-surface border-r border-line box-border
                     transition-[flex-basis,width] duration-200 ${mini ? "w-[60px] px-2 py-3" : "w-[244px] px-[10px] py-3"}
                     ${rail.overlay ? "fixed inset-y-0 left-0 z-40 shadow-e3" : ""}`}>
      <ul aria-label="Places" className="list-none m-0 p-0 flex flex-col gap-[2px]">
        <Place to="/" icon="home" label="Home" mini={mini} end
               inside={location.pathname.startsWith("/a/")} />
        <Place to="/registry/forging" icon="forge" label="Forge" mini={mini} />
        <Place to="/registry" icon="registry" label="Registry" mini={mini}
               end={false} not="/registry/forging" />
      </ul>
      <div role="separator" className="h-px bg-line-soft mx-1 my-[10px]" />

      {/* The slot: what is open. The collapse button lives with the bottom row, in one place. */}
      <div className="mb-1 flex flex-col">
        {rail.filled === 0 && !mini && (
          <Link to="/" className="px-[10px] py-[9px] rounded-control border border-dashed
                                  border-line-2 text-[13px] text-ink-3 no-underline hover:text-ink">
            Open an analysis…
          </Link>
        )}
        <div ref={rail.slotRef} className={`flex flex-col ${mini ? "gap-1" : ""} ${rail.filled === 0 ? "hidden" : ""}`} />
      </div>

      <div ref={rail.controlsRef} className="flex flex-col" />

      <div className="mt-auto pt-3 flex flex-col gap-1">
        <Jump mini={mini} />
        <div role="group" aria-label="This machine"
             className={`flex items-center border-t border-line-soft pt-2 ${mini ? "flex-col gap-[2px]" : "gap-1"}`}>
          {toggle}
          <Link to={settings} aria-label="Settings" title="Settings"
                className="w-11 h-11 sm:w-9 sm:h-9 rounded-control flex items-center justify-center text-ink-2 hover:bg-surface-2
                           hover:text-ink no-underline">
            <Icon name="settings" />
          </Link>
          <button type="button" onClick={() => setTheme(dark ? "light" : "dark")}
                  aria-label="Light or dark theme" title="Light / dark"
                  className="w-11 h-11 sm:w-9 sm:h-9 rounded-control flex items-center justify-center border-0 bg-transparent
                             text-ink-2 hover:bg-surface-2 hover:text-ink cursor-pointer">
            <Icon name="moon" />
          </button>
          <a href={DOCS_URL} target="_blank" rel="noreferrer" aria-label="Help" title="Help"
             className="w-11 h-11 sm:w-9 sm:h-9 rounded-control flex items-center justify-center text-ink-2 hover:bg-surface-2
                        hover:text-ink no-underline text-[15px] font-semibold">?</a>
          {!mini && (
            <span className="ml-auto flex items-center gap-[6px] text-[12px] text-ink-3 pr-2"
                  title="Comeni reads files on this machine">
              <span className="w-[7px] h-[7px] rounded-full bg-done" aria-hidden="true" />Local
            </span>
          )}
        </div>
      </div>
    </nav>
    </>
  );
}

/** A place: filled when you are on it; coloured but not filled when you are inside it. */
function Place({ to, icon, label, mini, end = true, not, inside = false }: {
  to: string; icon: IconName; label: string; mini: boolean; end?: boolean; not?: string; inside?: boolean;
}) {
  const location = useLocation();
  const excluded = not !== undefined && location.pathname.startsWith(not);
  return (
    <li>
      <NavLink to={to} end={end} title={label} aria-label={mini ? label : undefined}
               className={({ isActive }) => {
                 const on = isActive && !excluded;
                 return `flex items-center gap-[11px] rounded-control no-underline text-[14px] font-semibold
                         ${mini ? "w-10 h-10 mx-auto justify-center" : "px-[10px] py-2"}
                         ${on ? "bg-now-soft text-now-ink" : inside ? "text-now-ink hover:bg-surface-2"
                           : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`;
               }}>
        <Icon name={icon} />
        {!mini && <span>{label}</span>}
      </NavLink>
    </li>
  );
}
