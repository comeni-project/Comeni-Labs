import type { ReactNode } from "react";

/** Two workspaces and one lookup — `docs/design/forge-review.md` §3.
 *
 * Registry is a BUTTON rather than a nav item, deliberately: you consult it mid-decision,
 * and navigating away from a question you are answering is the friction the design removes.
 */
export function Shell({ children }: { children: ReactNode }) {
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
          <a href="#" className="px-3 py-1.5 text-body text-ink-2 no-underline rounded-r">Mendel</a>
          <a href="#" className="px-3 py-1.5 text-body font-semibold no-underline
                                 shadow-[inset_0_-2px_0_var(--pea)]">Forge</a>
        </div>

        <span className="w-px h-5 bg-line" />

        <div className="flex gap-[2px]">
          <a href="#" className="px-3 py-1.5 text-body font-semibold no-underline
                                 shadow-[inset_0_-2px_0_var(--pea)]">Queue</a>
          <a href="#" className="px-3 py-1.5 text-body text-ink-2 no-underline rounded-r">Contracts</a>
          <a href="#" className="px-3 py-1.5 text-body text-ink-2 no-underline rounded-r">Sources</a>
        </div>

        <button className="ml-auto text-body text-ink-2 bg-transparent border-0 cursor-pointer">
          Registry
        </button>
      </nav>
      {children}
    </div>
  );
}
