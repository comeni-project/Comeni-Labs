import { NavLink } from "react-router";

import type { AdaptationState } from "../../api/registry";

/** Status as a SHAPE plus a word, and the section's subnav.
 *
 * **Never colour alone** — §8, and it is not a preference: a reviewer who cannot distinguish
 * the yellow from the teal has to be able to tell *in review* from *adapted*, and about one
 * man in twelve cannot. So each state carries a distinct silhouette AND its own word, and
 * colour is the third signal rather than the only one.
 *
 * Drawn as clipped boxes rather than as glyphs, because a dingbat renders at whatever weight
 * the font has for it and disappears at 8px in half of them.
 */
const SHAPE: Record<string, { clip?: string; round?: boolean; hollow?: boolean; tone: string }> = {
  // A filled square: settled, and the quietest thing on the page.
  done: { tone: "bg-[var(--pea)]" },
  // A triangle: something is waiting on a person.
  review: { clip: "polygon(50% 0,100% 100%,0 100%)", tone: "bg-[var(--measured)]" },
  // A diamond: it stopped.
  fail: { clip: "polygon(50% 0,100% 50%,50% 100%,0 50%)", tone: "bg-[var(--fault)]" },
  // A circle: a worker is holding it.
  run: { round: true, tone: "bg-[var(--running)]" },
  // An outline: nothing has happened to it yet.
  open: { hollow: true, tone: "" },
};

/** Which shape a state wears, and what it is called on screen.
 *
 * **The label is the state's own word, not a friendlier one.** `changes_requested` reads as
 * *changes requested* and never as *rejected*: §1.6's whole argument is that a terminal word
 * makes an ordinary correction feel destructive, and a label is where that leaks back in.
 */
export const LOOK: Record<AdaptationState, { shape: keyof typeof SHAPE; label: string }> = {
  scaffolding: { shape: "run", label: "scaffolding" },
  queued: { shape: "open", label: "queued" },
  generating: { shape: "run", label: "generating" },
  validating: { shape: "run", label: "validating" },
  review: { shape: "review", label: "in review" },
  changes_requested: { shape: "open", label: "changes requested" },
  publishing: { shape: "run", label: "publishing" },
  published: { shape: "done", label: "published" },
  failed: { shape: "fail", label: "failed" },
  archived: { shape: "open", label: "archived" },
};

export function Mark({ shape }: { shape: keyof typeof SHAPE }) {
  const it = SHAPE[shape] ?? SHAPE.open;
  return (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 w-2 h-2 ${it.tone} ${it.round ? "rounded-full" : ""} ${
        it.hollow ? "border border-[var(--port-line)]" : ""
      }`}
      style={it.clip ? { clipPath: it.clip } : undefined}
    />
  );
}

/** A state, drawn and named.
 *
 * The word is the accessible name; the shape is `aria-hidden`. A screen reader that announced
 * both would say "triangle in review", which is the shape leaking into a channel it is not for.
 */
export function Status({ state }: { state: AdaptationState }) {
  const look = LOOK[state] ?? { shape: "open" as const, label: state };
  return (
    <span className="inline-flex items-center gap-2">
      <Mark shape={look.shape} />
      <span className="font-data text-label text-ink-3">{look.label}</span>
    </span>
  );
}

const tab = "px-3 py-1.5 font-data text-label tracking-[.08em] uppercase no-underline";

/** `Overview · Catalogue · Work queue`, below the global shell.
 *
 * **Below, and never in it** — §8 says so twice. Three section links in the global nav would
 * make the Registry read as three workspaces, and the global bar is where a person decides
 * which half of the product they are in rather than which page of one.
 */
/** A Registry page: the section subnav, then whatever the page is.
 *
 * **One root element, and that is the whole reason this exists.** `Shell` lays its children out
 * as `grid-rows-[auto_1fr] h-dvh` — a bar and a page — and every other screen in the product
 * returns a single element into it. These four returned a fragment of two, so the *subnav*
 * became the `1fr` row and stretched to fill the viewport: roughly 900 pixels of empty ground
 * between the tabs and the page, with the active tab's background painted down the left of it.
 *
 * **Invisible to the entire suite and obvious in a screenshot.** jsdom computes no layout, so
 * 421 frontend tests passed over it through Tasks 10 to 13; it took `_shots.py` and one look.
 * That is the 2026-09-01 lesson arriving for the third time — *reading finds wrong strings; it
 * does not find wrong pictures* — and it is why this wrapper is a component rather than a note
 * asking the next page to remember.
 */
export function Section({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-rows-[auto_1fr] min-h-0">
      <Subnav />
      {children}
    </div>
  );
}

/** A Registry page: the section subnav, then whatever the page is.
 *
 * **One root element, and that is the whole reason this exists.** `Shell` lays its children out
 * as `grid-rows-[auto_1fr] h-dvh` — a bar and a page — and every other screen in the product
 * returns a single element into it. These four returned a fragment of *two*, so the **subnav**
 * became the `1fr` row and stretched to fill the viewport: roughly 900 pixels of empty ground
 * between the tabs and the page, with the active tab's background painted down the left of it.
 *
 * **Invisible to the entire suite and obvious in one screenshot.** jsdom computes no layout, so
 * 421 frontend tests passed over it through Tasks 10 to 13; `.design/_shots.py` and one look
 * found it. That is the 2026-09-01 lesson arriving for the third time — *reading finds wrong
 * strings; it does not find wrong pictures* — and it is why this is a component rather than a
 * note asking the next page to remember.
 *
 * Named in full because `Catalogue.tsx` already has a local `Section` for the inspector's
 * labelled blocks, and two `Section`s in one import graph is a rename waiting to happen.
 */
export function RegistrySection({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-rows-[auto_1fr] min-h-0">
      <Subnav />
      {children}
    </div>
  );
}

export function Subnav() {
  return (
    <nav className="gutter flex gap-0.5 border-b border-line-soft" aria-label="Registry sections">
      {[
        ["/forge", "Overview"],
        ["/forge/catalogue", "Catalogue"],
        ["/forge/work", "Work queue"],
      ].map(([to, label]) => (
        <NavLink
          key={to}
          to={to}
          // `end` on the index route only: without it `/forge` matches every child and all
          // three tabs light up at once, which is the bug every nested nav has once.
          end={to === "/forge"}
          className={({ isActive }) =>
            `${tab} ${isActive ? "bg-surface text-ink" : "text-ink-3 hover:text-ink"}`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
