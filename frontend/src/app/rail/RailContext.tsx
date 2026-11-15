import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState,
  useSyncExternalStore, type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router";

import { useBrowserSetting } from "../../preferences/useBrowserSetting";

/** How a page puts its own things in the one rail (#511, "The rail's grammar").
 *
 * The rail is drawn once, by the shell; a page does not draw a rail of its own. It **portals**
 * into two places the rail holds open: the fixed slot (what is open: an analysis and its pages)
 * and the controls below the divider (this page's own, always labelled). A portal, not state
 * lifted into the shell, because the controls are live React trees (a folder tree, a review list)
 * that keep their own state and events where the page wrote them.
 *
 * A page that must have no rail at all (Welcome) says so with `<NoRail />`. */
type Rail = {
  slot: HTMLElement | null;
  controls: HTMLElement | null;
  slotRef: (el: HTMLElement | null) => void;
  controlsRef: (el: HTMLElement | null) => void;
  /** How many slot fillers are mounted: none means the dashed "Open an analysis…". */
  filled: number;
  hidden: number;
  count: (which: "filled" | "hidden", by: 1 | -1) => void;
  mini: boolean;
  setMini: (mini: boolean) => void;
  /** On a phone the rail is icons until opened, and then it lies over the page. */
  overlay: boolean;
};

const PHONE = "(max-width: 767px)";
const subscribePhone = (on: () => void) => {
  const query = window.matchMedia?.(PHONE);
  query?.addEventListener?.("change", on);
  return () => query?.removeEventListener?.("change", on);
};
const isPhone = () => window.matchMedia?.(PHONE).matches ?? false;

const RailContext = createContext<Rail | null>(null);

export function RailProvider({ children }: { children: ReactNode }) {
  const [slot, slotRef] = useState<HTMLElement | null>(null);
  const [controls, controlsRef] = useState<HTMLElement | null>(null);
  const [counts, setCounts] = useState({ filled: 0, hidden: 0 });
  const count = useCallback((which: "filled" | "hidden", by: 1 | -1) =>
    setCounts((c) => ({ ...c, [which]: c[which] + by })), []);
  const [stored, store] = useBrowserSetting("rail.mini", "false");
  const phone = useSyncExternalStore(subscribePhone, isPhone, () => false);
  const [open, setOpen] = useState(false);
  // Going somewhere closes the phone's open rail: it was opened to go there.
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  const value = useMemo<Rail>(() => ({
    slot, controls, slotRef, controlsRef, ...counts, count,
    mini: phone ? !open : stored === "true",
    setMini: (mini) => (phone ? setOpen(!mini) : store(String(mini))),
    overlay: phone && open,
  }), [slot, controls, counts, count, stored, store, phone, open]);
  return <RailContext.Provider value={value}>{children}</RailContext.Provider>;
}

export function useRail(): Rail {
  const rail = useContext(RailContext);
  if (!rail) throw new Error("useRail outside RailProvider");
  return rail;
}

function useCounted(which: "filled" | "hidden") {
  const { count } = useRail();
  useLayoutEffect(() => {
    count(which, 1);
    return () => count(which, -1);
  }, [count, which]);
}

/** Fills the rail's fixed slot: what is open. */
export function RailSlot({ children }: { children: ReactNode }) {
  const { slot } = useRail();
  useCounted("filled");
  return slot ? createPortal(children, slot) : null;
}

/** This page's controls, below the divider, under their label. */
export function RailControls({ label, children }: { label: string; children: ReactNode }) {
  const { controls, mini } = useRail();
  if (!controls || mini) return null;
  return createPortal(
    <>
      <div role="separator" className="h-px bg-line-soft mx-1 mt-[14px] mb-[10px]" />
      <div role="group" aria-label={label} className="flex flex-col">
        <div className="px-[10px] py-[6px] text-[11px] font-semibold tracking-[.07em] uppercase text-ink-3">
          {label}
        </div>
        {children}
      </div>
    </>,
    controls,
  );
}

/** This page has no rail (Welcome). */
export function NoRail() {
  useCounted("hidden");
  return null;
}
