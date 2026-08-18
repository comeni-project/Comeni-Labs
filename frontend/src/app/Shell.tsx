import { NavLink, Outlet } from "react-router";

/** Two workspaces and one lookup — `docs/design/forge-review.md` §3.
 *
 * Registry is a BUTTON rather than a nav item, deliberately: you consult it mid-decision,
 * and navigating away from a question you are answering is the friction the design removes.
 *
 * **What does not exist yet says so.** Mendel is 3C; Contracts and Sources are 3A phases 4
 * and 6. They are rendered `aria-disabled` rather than as links, because a link that goes
 * nowhere silently is worse than one that admits it — and six of those were what made slice
 * 1 look finished when nothing on the screen did anything.
 */
const nav = "px-3 py-1.5 text-body no-underline rounded-r";
const here = "font-semibold shadow-[inset_0_-2px_0_var(--pea)]";
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
      className={({ isActive }) => `${nav} ${isActive ? here : "text-ink-2"}`}
    >
      {children}
    </NavLink>
  );
}

export function Shell() {
  return (
    <div className="grid grid-rows-[54px_1fr] h-dvh">
      <nav className="flex items-center gap-7 px-6 bg-surface border-b border-line">
        <span className="flex items-baseline gap-2 font-display text-brand tracking-[-.015em]">
          <i className="w-[9px] h-[9px] self-center rounded-[50%_50%_50%_0] bg-pea rotate-[-45deg]" />
          Forge
          <small className="font-ui text-label uppercase tracking-[.13em] font-semibold text-ink-3">
            Comeni Labs
          </small>
        </span>

        <div className="flex gap-[2px] ml-2">
          <Soon title="The pipeline builder — Plan 3C">Mendel</Soon>
          <Tab to="/forge/queue">Forge</Tab>
        </div>

        <span className="w-px h-5 bg-line" />

        <div className="flex gap-[2px]">
          <Tab to="/forge/queue">Queue</Tab>
          <Soon title="What has landed — phase 4">Contracts</Soon>
          <Soon title="Where drafts come from — phase 6">Sources</Soon>
        </div>

        <button
          className={`ml-auto text-body bg-transparent border-0 ${gone}`}
          aria-disabled="true"
          title="Registry lookup — phase 2"
        >
          Registry
        </button>
      </nav>
      <Outlet />
    </div>
  );
}
