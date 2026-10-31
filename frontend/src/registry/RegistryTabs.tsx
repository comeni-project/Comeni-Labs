import { NavLink } from "react-router";

/** The Registry section's own bar (board 1): Catalogue, Forging and Releases. */
export function RegistryTabs({ registryAt }: { registryAt?: string }) {
  const tab = "px-[10px] py-[6px] rounded-control no-underline transition-colors";
  const on = "bg-surface text-ink font-semibold shadow-[inset_0_0_0_1px_var(--line)]";
  const off = "text-ink-2 hover:bg-hover hover:text-ink";
  return (
    <div className="border-b border-line bg-paper">
      <div className="frame gutter py-[9px] flex flex-wrap items-center gap-x-[26px] gap-y-1">
      <nav aria-label="Registry" className="flex flex-wrap gap-1">
        <NavLink to="/registry" end
                 className={({ isActive }) => `${tab} ${isActive ? on : off}`}>
          Catalogue
        </NavLink>
        <NavLink to="/registry/forging"
                 className={({ isActive }) => `${tab} ${isActive ? on : off}`}>
          Forging
        </NavLink>
        <NavLink to="/registry/releases"
                 className={({ isActive }) => `${tab} ${isActive ? on : off}`}>
          Releases
        </NavLink>
      </nav>
      {registryAt && (
        <span className="ml-auto min-w-0 pb-2 sm:pb-0 text-[12.5px] text-ink-3">
          Builder uses <span className="font-data text-ink break-all">comeni-registry {registryAt}</span>
        </span>
      )}
      </div>
    </div>
  );
}
