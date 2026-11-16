import { useId } from "react";

import { Tabs } from "../../ui/Tabs";

export type SideTab = "step" | "assistant";

/** Build's right panel (board: Build): the selected step, or the assistant. **Both stay mounted**
 *  while hidden, so a half-typed message or a scrolled conversation survives a look at a step. */
export function SidePanel({ tab, onTab, step, assistant }: {
  tab: SideTab;
  onTab: (tab: SideTab) => void;
  step: React.ReactNode;
  assistant: React.ReactNode;
}) {
  const id = useId();
  return (
    // `living-rail`: the builder's grid places it, and on a phone shows it or the canvas.
    <aside aria-label="Step and assistant" style={{ height: "var(--rail-h)" }}
           className="living-rail flex flex-col min-h-0 min-w-0 ml-[8px] mr-[28px] mt-[4px] mb-[24px] rounded-panel
                      border border-line bg-surface overflow-hidden">
      <div className="px-3 pt-2 border-b border-line-soft">
        <Tabs label="Panel" value={tab} onChange={onTab}
              tabs={[{ id: "step", label: "Step" }, { id: "assistant", label: "Assistant" }]} />
      </div>
      <div role="tabpanel" id={`${id}-step`} aria-label="Step" hidden={tab !== "step"} className="flex-1 min-h-0 overflow-auto">
        {step}
      </div>
      <div role="tabpanel" id={`${id}-assistant`} aria-label="Assistant" hidden={tab !== "assistant"}
           className="flex-1 min-h-0 flex flex-col">
        {assistant}
      </div>
    </aside>
  );
}
