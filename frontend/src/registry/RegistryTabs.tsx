import { NavLink } from "react-router";

/** The Registry section's own bar (board 1): Catalogue now; Forging and Releases drawn and
 *  disabled until the parts that bring them (forge MVP parts 2 and 5). */
export function RegistryTabs({ registryAt }: { registryAt?: string }) {
  const off = "py-3 text-ink-3 cursor-not-allowed";
  return (
    <div className="gutter flex flex-wrap items-center gap-x-[26px] gap-y-1 border-b border-line bg-paper">
      <nav aria-label="Registry" className="flex flex-wrap gap-[26px]">
        <NavLink
          to="/registry"
          end={false}
          className="py-3 text-ink font-semibold border-b-2 border-ink no-underline"
        >
          Catalogue
        </NavLink>
        <span aria-disabled="true" title="Forging comes in part 2" className={off}>Forging</span>
        <span aria-disabled="true" title="Releases come in part 5" className={off}>Releases</span>
      </nav>
      {registryAt && (
        <span className="ml-auto text-[12.5px] text-ink-3">
          Builder uses <span className="font-data text-ink">comeni-registry {registryAt}</span>
        </span>
      )}
    </div>
  );
}
