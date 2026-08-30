import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";

type Module = components["schemas"]["ModuleView"];

/** The card that opens beside the panel when you hover a module.
 *
 * **Beside the panel, not under the cursor** — `dashboard.md` §4. It is a card rather than a
 * tooltip because the content is a sentence, and it sits to the side so it never covers the rows
 * you are scanning.
 *
 * **The description is missing and the registry is why.** The design's card shows the thing you
 * would actually choose on — *"STAR is fastest but wants 32 GB; HISAT2 is the low-memory
 * alternative"* — and `ModuleContract` has no field for it: no `summary`, and `priority_because`
 * is empty on all twelve shipped contracts. So the card shows what a contract genuinely knows.
 * Issue #78 is the missing field; a blank where prose should be would have been worse than an
 * honest absence.
 */
function Card({ module: m, top }: { module: Module; top: number }) {
  return (
    <div
      data-testid="module-card"
      style={{ top }}
      className="absolute left-full ml-3 z-20 w-[300px] rounded-r border border-line
                 bg-surface p-4 shadow-e3"
    >
      <h4 className="m-0 font-data text-body font-semibold text-ink">{m.process}</h4>
      <p className="mt-1 mb-0 text-secondary text-ink-3 font-data">{m.contract_id}</p>
      <dl className="mt-3 mb-0 grid grid-cols-[52px_1fr] gap-x-3 gap-y-1 text-secondary">
        <dt className="text-ink-3">Needs</dt>
        <dd className="m-0 font-data text-ink-2">{m.needs.join(", ") || "—"}</dd>
        <dt className="text-ink-3">Makes</dt>
        <dd className="m-0 font-data text-ink-2">{m.makes.join(", ") || "—"}</dd>
        <dt className="text-ink-3">Role</dt>
        <dd className="m-0 font-data text-ink-2">{m.roles.join(", ") || "—"}</dd>
      </dl>
      <p className="mt-3 mb-0 text-label text-ink-3">
        {/* Said on the screen rather than left as a gap. */}
        No description — the registry has no field for one yet (#78).
      </p>
    </div>
  );
}

/** Every module a pipeline can be built from, grouped by the job it does.
 *
 * **All of them, not the ones already on the canvas.** A picker you drag from cannot list only
 * what is already there. Grouped by role because that is the question a person asks — *what
 * aligns reads* — rather than by name.
 */
/** The MIME type a dragged module travels under.
 *
 * A custom type rather than `text/plain`: the canvas must not accept a paragraph somebody
 * dragged out of another window and try to add it as a tool.
 */
export const MODULE_DND = "application/x-mendel-contract";

export function Modules({
  inPipeline,
  onAdd,
}: {
  inPipeline: Set<string>;
  /** Add this contract to the pipeline. Omitted where the list is reference-only. */
  onAdd?: (contractId: string) => void;
}) {
  const [hovered, setHovered] = useState<{ module: Module; top: number } | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["modules"],
    queryFn: () => get<Module[]>("/pipeline/modules"),
  });

  if (isLoading) return <p className="px-4 py-3 text-secondary text-ink-3">Reading modules…</p>;

  const byRole = new Map<string, Module[]>();
  for (const module of data ?? []) {
    const role = module.roles[0] ?? "unclassified";
    byRole.set(role, [...(byRole.get(role) ?? []), module]);
  }

  return (
    <div className="relative" onMouseLeave={() => setHovered(null)}>
      {[...byRole.entries()].map(([role, modules]) => (
        <div key={role}>
          <div className="px-4 pt-3 pb-1 text-label uppercase tracking-[.13em] font-semibold text-ink-3">
            {role.replace(/_/g, " ")}
          </div>
          {modules.map((module) => (
            <div
              key={module.contract_id}
              data-testid="module-row"
              data-in-pipeline={inPipeline.has(module.contract_id) || undefined}
              // **Draggable for real now.** Plan 3C made this `draggable` with an `onDragStart`
              // that set data nothing read, then removed both — a control that moves under your
              // hand and does nothing is worse than one plainly not offered. Its note said
              // "adding a module to a pipeline is not expressible in the engine today", which a
              // `DraftGraph` makes false: a drawn graph pins whatever you put in it.
              //
              // **Double-click adds too**, because drag-and-drop is the gesture people miss and
              // a list you can only drag from is a list half the users cannot use.
              draggable={onAdd !== undefined}
              // **Reachable without a mouse**, and it was not until Plan 4 phase 3a. This was a
              // bare `div draggable="true"` with no `role`, no `tabIndex` and no key handler —
              // absent from the accessibility tree entirely, so drag and double-click were the
              // only two ways to add a step and a keyboard user had none.
              //
              // `role="button"` rather than a real `<button>`: a button element cannot be
              // `draggable` in Firefox, and dropping the drag to gain the semantics would trade
              // one group of users for another. The handler below is what a button would give.
              role={onAdd ? "button" : undefined}
              tabIndex={onAdd ? 0 : undefined}
              onKeyDown={(e) => {
                if (!onAdd) return;
                if (e.key !== "Enter" && e.key !== " ") return;
                // Space scrolls the panel otherwise, which moves the list under the selection.
                e.preventDefault();
                onAdd(module.contract_id);
              }}
              onDragStart={(e) => {
                e.dataTransfer.setData(MODULE_DND, module.contract_id);
                e.dataTransfer.effectAllowed = "copy";
              }}
              onDoubleClick={() => onAdd?.(module.contract_id)}
              // The card follows the keyboard as well as the pointer, or tabbing through the
              // list tells you the tool's name and nothing about what it needs or makes.
              onFocus={(e) => setHovered({ module, top: e.currentTarget.offsetTop })}
              title={onAdd ? "drag onto the canvas, double-click, or press Enter" : undefined}
              onMouseEnter={(e) =>
                setHovered({ module, top: e.currentTarget.offsetTop })
              }
              className={`px-4 py-1.5 flex items-baseline gap-2 hover:bg-surface-2
                         focus-visible:shadow-[var(--ring)] focus-visible:outline-none
                         data-[in-pipeline]:font-semibold
                         ${onAdd ? "cursor-grab active:cursor-grabbing" : "cursor-default"}`}
            >
              <span className="font-data text-body text-ink truncate">{module.tool}</span>
              {inPipeline.has(module.contract_id) && (
                <span
                  title="already in this pipeline"
                  className="ml-auto w-1.5 h-1.5 rounded-full bg-pea shrink-0 self-center"
                />
              )}
            </div>
          ))}
        </div>
      ))}
      {hovered && <Card module={hovered.module} top={hovered.top} />}
      <p className="px-4 py-3 text-label text-ink-3 m-0">
        {onAdd
          ? "Drag onto the canvas, or double-click, to add a step."
          : "Reference only. This canvas shows what the engine resolved."}
      </p>
    </div>
  );
}
