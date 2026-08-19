import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { Glossary } from "../ui/Glossary";
import { useKeys } from "./useKeys";

/** The frame: identity, then two workspaces, then the sections of the one you are in.
 *
 * **The wordmark is the whole identity and it goes home.** It said `Forge · Comeni Labs` on
 * every screen, which was true while `/` redirected into the forge and every destination was a
 * forge screen. 3B made `/` a real page and 3C adds a half that is not the forge either, so a
 * wordmark naming one workspace was claiming the product is that workspace. Naming the site is
 * the fix that stays true as halves are added.
 *
 * **`Builder` became a link in Plan 3C phase 3**, and `Soon` went with it — nothing is disabled
 * here any more. It was `aria-disabled` for the whole of 3A, 3B and 3D on the rule that a link
 * going nowhere silently is worse than one that admits it; six of those were what made slice 1
 * look finished when nothing on the screen did anything. The rule stands and `Soon` is deleted
 * rather than kept for a future occupant, because a component with no caller is a component that
 * rots.
 *
 * **`?` opens the glossary, from anywhere.** Eight words appear on these screens without ever
 * being defined — contract, role, type, measurement, drift, hole, band, proposal — and the
 * verdict on 2026-08-19 was that the person who co-designed the system could not read its own
 * interface. It lives in the shell rather than on a page so it is reachable from the screen you
 * are confused by rather than from a screen you have to go and find.
 *
 * **There is no Registry box.** It was a text input in the nav that took a type id from memory
 * and opened a panel — the operator's verdict was *ugly, unintuitive and useless*, and the
 * design argument behind it does not survive contact: `forge-review.md` §3 wanted the registry
 * consulted *mid-decision*, and the way you consult a type mid-decision is by clicking the type
 * you are looking at, not by retyping it into a box in the corner. The panel went with the box
 * rather than staying reachable by nothing. When it returns it should hang off a type id.
 */
const nav = "px-3 py-1.5 text-body no-underline rounded-r transition-colors";
const here = "font-semibold text-ink shadow-[inset_0_-2px_0_var(--pea)]";

function Tab({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `${nav} ${isActive ? here : "text-ink-2 hover:text-ink"}`
      }
    >
      {children}
    </NavLink>
  );
}

export function Shell() {
  const [helping, setHelping] = useState(false);
  useKeys({ "?": () => setHelping(true), escape: () => setHelping(false) });

  return (
    <div className="grid grid-rows-[54px_1fr] h-dvh">
      <nav className="flex items-center gap-7 px-6 bg-surface border-b border-line">
        <Link
          to="/"
          aria-label="Comeni Labs — home"
          className="flex items-baseline gap-2 font-display text-brand tracking-[-.015em]
                     text-ink no-underline"
        >
          <i className="w-[9px] h-[9px] self-center rounded-[50%_50%_50%_0] bg-pea rotate-[-45deg]" />
          Comeni Labs
        </Link>

        <div className="flex gap-[2px] ml-2">
          <Tab to="/build">Builder</Tab>
          <Tab to="/forge/queue">Forge</Tab>
        </div>

        <span className="w-px h-5 bg-line" />

        <div className="flex gap-[2px]">
          {/* **Two, not three.** `Contracts` and `Sources` were the same list at two stages of
              one tool's life, and naming them separately is what taught a person that a tool is
              one thing here and another thing there — spec §1.3. */}
          <Tab to="/forge/queue">Queue</Tab>
          <Tab to="/forge/tools">Tools</Tab>
        </div>

        <button
          onClick={() => setHelping(true)}
          title="What the words mean"
          className="ml-auto px-2 py-1 rounded-r bg-transparent border border-line
                     cursor-pointer text-secondary text-ink-3 hover:text-ink hover:border-line-2"
        >
          What the words mean <span className="font-data">?</span>
        </button>
      </nav>
      <Outlet />
      {helping && <Glossary onClose={() => setHelping(false)} />}
    </div>
  );
}
