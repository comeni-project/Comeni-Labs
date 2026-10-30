import { NavLink } from "react-router";

/** The Registry section's own bar (board 1): Catalogue, Forging and Releases. */
export function RegistryTabs({ registryAt }: { registryAt?: string }) {
  const on = "text-ink font-semibold border-b-2 border-ink";
  return (
    <div className="gutter flex flex-wrap items-center gap-x-[26px] gap-y-1 border-b border-line bg-paper">
      <nav aria-label="Registry" className="flex flex-wrap gap-[26px]">
        <NavLink to="/registry" end
                 className={({ isActive }) => `py-3 no-underline ${isActive ? on : "text-ink-2"}`}>
          Catalogue
        </NavLink>
        <NavLink to="/registry/forging"
                 className={({ isActive }) => `py-3 no-underline ${isActive ? on : "text-ink-2"}`}>
          Forging
        </NavLink>
        <NavLink to="/registry/releases"
                 className={({ isActive }) => `py-3 no-underline ${isActive ? on : "text-ink-2"}`}>
          Releases
        </NavLink>
      </nav>
      {registryAt && (
        <span className="ml-auto min-w-0 pb-2 sm:pb-0 text-[12.5px] text-ink-3">
          Builder uses <span className="font-data text-ink break-all">comeni-registry {registryAt}</span>
        </span>
      )}
    </div>
  );
}
