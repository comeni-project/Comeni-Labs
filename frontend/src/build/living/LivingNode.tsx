import type { PortView } from "../../api/types";
import { HEAD_H, NODE_H, NODE_W, PORT_ROW } from "../geometry";
import type { Author } from "./format";
import { processName } from "./format";

/** One step on the living canvas — the 172×112 symbol every canvas in the product draws.
 *
 * **Geometry from `geometry.ts`, never a literal here.** A wire lands on a port because both read
 * one derivation; the 2026-08-30 walk found `NODE_W` at 232 in the browser and 172 in Python the
 * one time a component kept its own.
 *
 * Two encodings, and they compose rather than collide:
 *
 * - **tier is colour**, on the left bar — settled spends none, measured is amber, open is red;
 * - **author is stroke**, on the same bar — solid for the resolver, dashed for a model, and a
 *   notch at the midpoint where a person chose.
 *
 * A **ghost** is dashed on its *outer* border and keeps a solid left bar, because a dashed left
 * bar already means *a model chose this* — the design record's one real bug was a ghost that
 * dashed every border and made every proposal read as model-authored.
 */
export function LivingNode({
  id,
  at,
  tier,
  author,
  ports,
  settled,
  ghost = false,
  selected = false,
  onSelect,
}: {
  id: string;
  at: { x: number; y: number };
  tier: number;
  author: Author;
  ports: PortView[];
  /** How many values this step settled. **Absent on a ghost**: a number it does not have yet is
   *  the fastest way to make provisional read as committed. */
  settled?: number;
  ghost?: boolean;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const bar = tier === 4 ? "var(--undecided)" : tier === 3 ? "var(--measured)" : "var(--rail)";
  const rows = ports.slice(0, Math.floor((NODE_H - HEAD_H - 24) / PORT_ROW));

  return (
    <button
      type="button"
      data-node={id}
      data-testid={`living-node-${id}`}
      data-ghost={ghost || undefined}
      data-author={author}
      aria-pressed={selected}
      aria-label={`${processName(id)}${ghost ? ", proposed" : ""}`}
      onClick={onSelect}
      className="absolute flex flex-col text-left p-0 cursor-pointer focus-visible:shadow-[var(--ring)]"
      style={{
        left: at.x,
        top: at.y,
        width: NODE_W,
        height: NODE_H,
        background: ghost ? "var(--panel)" : "var(--node)",
        opacity: ghost ? 0.62 : 1,
        border: `1px ${ghost ? "dashed" : "solid"} ${selected ? "var(--link)" : "var(--node-line)"}`,
        borderLeft: `3px ${author === "model" ? "dashed" : "solid"} ${selected ? "var(--link)" : bar}`,
        boxShadow: selected ? "0 0 0 1px color-mix(in oklab, var(--link) 26%, transparent)" : undefined,
      }}
    >
      {author === "person" && !ghost && (
        <span
          aria-hidden
          data-testid="notch"
          className="absolute"
          style={{ left: -3, top: 49, width: 3, height: 14, background: bar }}
        />
      )}
      <span
        className="flex items-center gap-2 px-[10px] w-full shrink-0"
        style={{ height: HEAD_H, borderBottom: `1px solid ${ghost ? "var(--line-soft)" : "var(--node-rule)"}` }}
      >
        <span className="font-data text-[11px] font-medium text-ink truncate">{processName(id)}</span>
        {ghost && (
          <span className="ml-auto font-data text-[8.5px] tracking-[.08em] text-link">PROPOSED</span>
        )}
      </span>
      {/* **No top padding, measured rather than read.** The artboard's CSS says `padding:5px 0`,
          and its render puts the first row's centre at 306 — the header rule plus half a row.
          With the padding, the third row clipped into the footer. The picture is the spec. */}
      <span className="flex-1 min-h-0 pb-[5px] w-full overflow-hidden">
        {rows.map((port) => (
          <span
            key={`${port.side}:${port.name}`}
            className="flex items-center gap-[7px] px-[10px] font-data text-[8.5px]"
            style={{ height: PORT_ROW }}
          >
            <span aria-hidden className="text-ink-4">·</span>
            <span className={port.side === "in" ? "text-ink-2 truncate" : "text-ink-3 truncate"}>
              {port.type_id}
              {port.states.length > 0 ? `[${port.states.join(", ")}]` : ""}
            </span>
          </span>
        ))}
      </span>
      {!ghost && (
        <span
          className="h-[24px] flex items-center px-[10px] w-full shrink-0 font-data text-[9px] text-ink-3"
          style={{ borderTop: "1px solid var(--node-rule)" }}
        >
          {settled ?? 0} settled
        </span>
      )}
    </button>
  );
}
