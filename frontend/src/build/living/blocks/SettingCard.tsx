import { useId, useState } from "react";

import type { AuthoringBlock } from "../../../api/types";
import { processName } from "../format";
import { BlockFrame, Primary } from "./parts";

type SettingBlock = Extract<AuthoringBlock, { kind: "setting_request" }>;

/** A value the engine could not settle, asked as a question with its declared domain.
 *
 * **Offered values render as a choice; an open domain renders as a field**, and the value goes
 * to the server as a draft edit where `HumanParamValue` refuses a path-shaped string and the
 * server stamps it as the person's. The card does not validate a value itself: a second copy of
 * the rule in the browser is a copy that can be looser than the one that counts.
 */
export function SettingCard({
  block,
  onApply,
}: {
  block: SettingBlock;
  onApply: (node: string, setting: string, value: string) => void;
}) {
  const field = useId();
  const [value, setValue] = useState(block.current ?? "");
  const closed = block.options.length > 0;

  return (
    <BlockFrame
      label={`a value for ${block.setting}`}
      title={`${processName(block.node)} · ${block.setting}`}
      aside={block.current ? `now ${block.current}` : "not set"}
      actions={
        <Primary
          data-testid={`apply-${block.setting}`}
          disabled={value.trim() === ""}
          onClick={() => onApply(block.node, block.setting, value.trim())}
        >
          Use this value
        </Primary>
      }
    >
      <p className="m-0 mb-2 text-[12.5px] text-ink">{block.reason}</p>
      {block.premise && <p className="m-0 mb-3 text-[11.5px] text-ink-3">{block.premise}</p>}
      {closed ? (
        <div role="radiogroup" aria-label={`values for ${block.setting}`}>
          {block.options.map((option) => (
            <label key={option.id} className="flex items-center gap-2 mb-[6px] text-[12.5px] text-ink cursor-pointer">
              <input type="radio" name={field} value={option.label} checked={value === option.label}
                     onChange={() => setValue(option.label)} className="accent-[var(--link)]" />
              {option.label}
              {option.recommended && <span className="font-data text-[9.5px] text-link">recommended</span>}
            </label>
          ))}
        </div>
      ) : (
        <label className="block">
          <span className="sr-only">{`a value for ${block.setting}`}</span>
          <input id={field} value={value} onChange={(e) => setValue(e.target.value)}
                 placeholder="type a value"
                 className="w-full font-data text-[12px] bg-transparent text-ink border px-2 py-[5px]"
                 style={{ borderColor: "var(--line-2)" }} />
        </label>
      )}
    </BlockFrame>
  );
}
