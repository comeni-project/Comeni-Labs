import type { components } from "../api/schema";
import { Modules } from "./Modules";

type Built = components["schemas"]["BuiltPipeline"];

/** What could I add.
 *
 * ═══ THE `In pipeline` LIST IS DELETED, ON PURPOSE ════════════════════════════════════════
 *
 * Plan 4 phase 3a, `impl-settled`: *the left steps list is deleted on purpose. It duplicated
 * the canvas. Orientation is the minimap's job. Do not bring back a third column.*
 *
 * The file it lived in argued for both tabs — *`In pipeline` answers where is that step, and
 * `All modules` answers what could I add* — and the first question is one the canvas beside it
 * already answers, in the same order, with the wires drawn in. A table of contents for a picture
 * you are looking at is a second place for the two to disagree.
 *
 * ═══ THIS PALETTE IS ITSELF TEMPORARY ═════════════════════════════════════════════════════
 *
 * **3b replaces it with the browse overlay** — search, filters, the type signature as the
 * description, and a tool appearing under EVERY role it declares rather than `roles[0]`. It is
 * kept here rather than deleted with the list because deleting both at once would leave no way
 * to add a step at all between two commits, and a product that cannot be used in between is not
 * a product that is being built incrementally.
 */
export function LeftPanel({
  onAdd,
  data,
}: {
  data: Built;
  /** Add a contract to the pipeline. Threaded through to `Modules`. */
  onAdd?: (contractId: string) => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-line">
        <span className="px-2 py-1 text-secondary text-ink-3">All modules</span>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <Modules
          inPipeline={new Set(data.steps.map((step) => step.contract_id))}
          onAdd={onAdd}
        />
      </div>
    </div>
  );
}
