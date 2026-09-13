import { useState } from "react";

import type { AuthoringBlock } from "../../../api/types";
import { processName } from "../format";
import { BlockFrame, Primary, Secondary } from "./parts";

type ChangeBlock = Extract<AuthoringBlock, { kind: "change_set" }>;

/** A change that touches several steps, shown exactly before it is applied.
 *
 * **Two presses, and the second names what it will do.** A change parsed from a sentence that
 * removes or replaces more than one step is the easiest way to lose work in a conversation — so
 * the card lists every step it removes, adds and resets, and *Apply* becomes *Remove 2 steps* on
 * the first press rather than acting on it.
 */
export function ChangeSetCard({
  block,
  onApply,
}: {
  block: ChangeBlock;
  onApply: (block: ChangeBlock) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const removing = block.removes.length;

  return (
    <BlockFrame
      label="the change this would make"
      title="This would change"
      actions={
        confirming ? (
          <>
            <Primary data-testid="confirm-change" onClick={() => onApply(block)}>
              {removing > 0
                ? `Remove ${removing} step${removing === 1 ? "" : "s"}`
                : "Apply these changes"}
            </Primary>
            <Secondary onClick={() => setConfirming(false)}>Keep things as they are</Secondary>
          </>
        ) : (
          <Primary data-testid="apply-change" onClick={() => setConfirming(true)}>
            Apply…
          </Primary>
        )
      }
    >
      <p className="m-0 mb-2 text-[12.5px] text-ink">{block.summary}</p>
      <ul aria-label="affected steps" className="m-0 p-0 font-data text-[11px]">
        {block.removes.map((node) => (
          <li key={`-${node}`} className="list-none text-[var(--undecided)]">
            − {processName(node)} <span className="text-ink-3">removed</span>
          </li>
        ))}
        {block.adds.map((node) => (
          <li key={`+${node}`} className="list-none text-ink">
            + {processName(node)} <span className="text-ink-3">proposed next</span>
          </li>
        ))}
        {block.settings.map((setting) => (
          <li key={`~${setting}`} className="list-none text-ink-2">~ {setting} <span className="text-ink-3">reset</span></li>
        ))}
      </ul>
    </BlockFrame>
  );
}
