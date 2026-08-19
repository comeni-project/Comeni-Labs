import { Link, NavLink, Outlet } from "react-router";

/** The frame: identity, then two workspaces, then the sections of the one you are in.
 *
 * **The wordmark is the whole identity and it goes home.** It said `Forge · Comeni Labs` on
 * every screen, which was true while `/` redirected into the forge and every destination was a
 * forge screen. 3B made `/` a real page and 3C adds a half that is not the forge either, so a
 * wordmark naming one workspace was claiming the product is that workspace. Naming the site is
 * the fix that stays true as halves are added.
 *
 * **What does not exist yet says so.** The Builder — Mendel's canvas — is 3C. It is rendered
 * `aria-disabled` rather than as a link, because a link that goes nowhere silently is worse
 * than one that admits it, and six of those were what made slice 1 look finished when nothing
 * on the screen did anything.
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
const gone = "text-ink-3 cursor-not-allowed";

function Soon({ children, title }: { children: string; title: string }) {
  return (
    <span className={`${nav} ${gone}`} aria-disabled="true" title={title}>
      {children}
    </span>
  );
}

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
          <Soon title="The pipeline canvas — Plan 3C">Builder</Soon>
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
      </nav>
      <Outlet />
    </div>
  );
}
