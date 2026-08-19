import { useState } from "react";

import type { components } from "../api/schema";
import { Modules } from "./Modules";
import { Steps } from "./Steps";

type Built = components["schemas"]["BuiltPipeline"];

/** Two lists, two questions.
 *
 * **`In pipeline` answers *where is that step*** — the running order, so you can find a box
 * without hunting the canvas for it. **`All modules` answers *what could I add*** — every landed
 * contract, grouped by role, draggable.
 *
 * They were one list for a phase, and the one they were was the wrong one: 3C shipped only the
 * in-pipeline list, which is a table of contents rather than a picker. Both are kept because both
 * are asked, and collapsing them again would lose whichever half went.
 */
export function LeftPanel({
  data,
  selected,
  onSelect,
}: {
  data: Built;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [tab, setTab] = useState<"pipeline" | "all">("pipeline");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-line">
        {(["pipeline", "all"] as const).map((one) => (
          <button
            key={one}
            data-testid={`left-tab-${one}`}
            data-active={tab === one || undefined}
            onClick={() => setTab(one)}
            className="px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer
                       text-secondary text-ink-3 hover:text-ink
                       data-[active]:text-ink data-[active]:font-semibold
                       data-[active]:shadow-[inset_0_-2px_0_var(--pea)]"
          >
            {one === "pipeline" ? "In pipeline" : "All modules"}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {tab === "pipeline" ? (
          <Steps data={data} selected={selected} onSelect={onSelect} />
        ) : (
          <Modules inPipeline={new Set(data.steps.map((step) => step.contract_id))} />
        )}
      </div>
    </div>
  );
}
