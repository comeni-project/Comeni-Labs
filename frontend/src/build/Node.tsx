import type { components } from "../api/schema";
import { NODE_H, NODE_W, portOffset } from "./geometry";
import { Port } from "./Port";

type Placed = components["schemas"]["PlacedNode"];
type Step = components["schemas"]["StepView"];
type PortView = components["schemas"]["PortView"];

/** The tier, drawn as the node's **left border** — 3px, and settled spends no colour at all.
 *
 * `impl-inv` on the redesign canvas is explicit, and it is the rule this table exists to keep:
 *
 * > THE TIER LADDER on the canvas: settled gets NO COLOUR AT ALL. Only measured (amber) and
 * > open (red) spend any. Colour where something needs you, nowhere else.
 *
 * It shipped as a 4px inner div in `--pea` for tiers 1 and 2 — so a graph where nothing needed
 * you was a wall of green, and the two nodes that did need you had to compete with it. A canvas
 * that colours everything has no way left to say *look here*.
 *
 * `--rail` is a neutral slate, which is what `BuilderCanvas.dc.html` gives `.node` by default;
 * `.meas` and `.open` are the only classes that override it.
 */
const RAIL: Record<number, string> = {
  1: "var(--rail)",
  2: "var(--rail)",
  3: "var(--measured)",
  4: "var(--undecided)",
};

/** One step on the canvas.
 *
 * **Dragged in the view only.** Nothing persists a node position and 3C is not the phase to add
 * somewhere to put one — the layout is deterministic precisely so that it does not need to be
 * stored. A drag is a person looking closer, not an edit.
 */
export function Node({
  placed,
  step,
  zoom,
  dim = false,
  selected,
  onSelect,
  onContextMenu,
  onOpenSettings,
  offset,
  onDrag,
  dragging,
  onStartWire,
  onFinishWire,
  onMoving,
  onExplore,
  verdictFor,
}: {
  placed: Placed;
  step: Step | undefined;
  zoom: number;
  dim?: boolean;
  selected: boolean;
  onSelect: () => void;
  /** Right-click. The canvas opens a menu; a read-only canvas passes nothing and the browser's
   *  own menu is left alone. */
  onContextMenu?: (e: React.MouseEvent) => void;
  onOpenSettings?: () => void;
  /** Where this node is, absolutely. The client owns it; the server's layout seeded it. */
  offset: { x: number; y: number };
  onDrag: (by: { x: number; y: number }) => void;
  /** Which output a wire is being dragged from, anywhere on the canvas. `null` most of the
   *  time, and when it is null every port renders exactly as it did before this existed. */
  dragging?: { node: string; port: string } | null;
  onStartWire?: (port: string) => void;
  onFinishWire?: (port: string) => void;
  /** How an input port should look during someone else's drag. A lookup into the server's
   *  compatibility index — never a decision made here. */
  verdictFor?: (port: string) => "yes" | "conventional-no" | "no" | undefined;
  /** Called `true` when this node starts moving and `false` when it stops. The canvas draws
   *  its measuring grid only in between. */
  onMoving?: (moving: boolean) => void;
  /** Somebody double-clicked a port and wants to know what could go on the other end. */
  onExplore?: (port: PortView) => void;
}) {

  const onPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    const sx = e.clientX;
    const sy = e.clientY;
    const from = offset;
    // **The canvas needs to know a node is moving**, because the grid exists only while
    // something is. Reported upward for the same reason the position is: it is a fact about
    // the canvas, not about this box.
    onMoving?.(true);
    const move = (ev: PointerEvent) =>
      // **Divided by the zoom**, or a node at 50% travels twice as far as the cursor.
      // **Reported upward, not kept here.** It was local state, which meant a dragged node left
      // its wires behind — the graph broke the moment you touched it, which is worse than a
      // graph you cannot rearrange.
      onDrag({ x: from.x + (ev.clientX - sx) / zoom, y: from.y + (ev.clientY - sy) / zoom });
    const up = () => {
      onMoving?.(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const ports = step?.ports ?? [];
  const ins = ports.filter((port) => port.side === "in");
  const outs = ports.filter((port) => port.side === "out");
  const settings = step?.settings ?? [];
  const needing = settings.filter((setting) => setting.tier === 4).length;
  const measured = settings.some((setting) => setting.tier === 3);
  const settled = settings.length - needing;
  const open = needing > 0;

  return (
    <div
      data-node
      data-testid="node"
      data-id={placed.id}
      data-tier={placed.tier}
      data-selected={selected || undefined}
      data-dim={dim || undefined}
      onPointerDown={onPointerDown}
      onContextMenu={onContextMenu}
      onClick={onSelect}
      style={{
        // **Absolute, from the client's own position.** It was `placed.x + offset.x` — the
        // server's coordinate plus a drag delta — so a node the server had not laid out yet had
        // nowhere to be, and an added step could not appear until a round trip came back.
        left: `${Math.round(offset.x)}px`,
        top: `${Math.round(offset.y)}px`,
        // **One symbol, 172×112, for every process** — `impl-geom` calls this load-bearing:
        // variable heights put a jog between every pair and the main chain stops reading as a
        // chain.
        width: NODE_W,
        height: NODE_H,
        background: "var(--node)",
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: "var(--node-line)",
        // The tier is the LEFT BORDER, not an inner bar — so it cannot take width from the
        // content and cannot be mistaken for a fill.
        borderLeftWidth: 3,
        borderLeftColor: open
          ? "var(--undecided)"
          : measured
            ? "var(--measured)"
            : RAIL[placed.tier] ?? "var(--rail)",
      }}
      className="absolute flex flex-col cursor-grab active:cursor-grabbing
                 data-[selected]:shadow-[0_0_0_1px_var(--link)]
                 data-[dim]:opacity-20 transition-[box-shadow,opacity]"
    >
      {/* Ports sit ON the edges, at the one derivation — `portOffset`. An input on the left, an
          output on the right, because that is the way the graph flows. */}
      {ins.map((port, i) => (
        <Port key={`in.${port.name}`} port={port} side="in" y={portOffset(i)}
              verdict={dragging ? verdictFor?.(port.name) : undefined}
              onExplore={() => onExplore?.(port)}
              onFinishWire={() => onFinishWire?.(port.name)} />
      ))}
      {outs.map((port, i) => (
        <Port key={`out.${port.name}`} port={port} side="out" y={portOffset(i)}
              onExplore={() => onExplore?.(port)}
              onStartWire={() => onStartWire?.(port.name)} />
      ))}

      {/* ── The header: the name, and the way into its settings ───────────────────────── */}
      <div className="flex items-center gap-2 h-[28px] px-[10px] shrink-0"
           style={{ borderBottomWidth: 1, borderBottomStyle: "solid",
                    borderBottomColor: "var(--node-rule)" }}>
        <span className="font-data text-[11px] font-medium text-ink truncate">
          {step?.process ?? placed.id}
        </span>
        {step && (
          // **`⋯` on every node** — the artboard puts it in each header, and the settings live
          // in a card on the node. `impl-settled`: *the rail is about the CHOICE, the card is
          // about the VALUES. Two lists of the same thing is what we just removed.*
          <button
            data-testid="open-settings"
            aria-label={`settings for ${step.process}`}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onOpenSettings?.(); }}
            className="ml-auto font-data text-[11px] leading-none bg-transparent border-0 p-0
                       cursor-pointer text-ink-3 hover:text-ink"
          >
            ⋯
          </button>
        )}
      </div>

      {/* ── The rows: the TYPES, on the node ─────────────────────────────────────────────
          `n-bcanvas`: *types on the node*. They were on the wire labels, so reading what a step
          consumes meant tracing a line to its far end. */}
      <div className="flex-1 min-h-0 py-[5px] overflow-hidden">
        {ports.slice(0, 4).map((port) => (
          <div key={`${port.side}.${port.name}`}
               className="flex items-center gap-[7px] h-[19px] px-[10px] font-data text-[8.5px]">
            <span aria-hidden style={{ color: "var(--port-line)" }}>
              {port.side === "in" ? "◀" : "▶"}
            </span>
            <span className={port.side === "in" ? "text-ink-2 truncate" : "text-ink-3 truncate"}>
              {port.type_id || port.name}
            </span>
          </div>
        ))}
      </div>

      {/* ── The footer: what could need you, and the contract when nothing does ─────────
          Invariant 6 — an open value shows on the node, in the status line, in the settings
          card and in the run sheet. Four places is the honesty mechanism, not redundancy. */}
      <div data-testid="node-foot"
           className="h-[24px] flex items-center gap-1 px-[10px] shrink-0 font-data text-[9px]
                      text-ink-3"
           style={{ borderTopWidth: 1, borderTopStyle: "solid",
                    borderTopColor: "var(--node-rule)" }}>
        {/* **`2 need you · 11 settled`**, which is the artboard verbatim. Invariant 6 — an open
            value shows on the node, in the status line, in the settings card and in the run
            sheet; this is the first of the four.

            **A MEASURED value is not counted here**, and that is the artboard's choice rather
            than an omission: the `.meas` node's footer reads plainly `14 settled` and the amber
            left border carries the whole signal. Tier 3 says *the machinery worked, check the
            premise* — it is not a thing waiting on you, and putting it in the same sentence as
            the count that is would flatten the difference the tier ladder exists to draw. */}
        {open && <span style={{ color: "var(--undecided)" }}>{needing} need you</span>}
        {open && settled > 0 && <span aria-hidden>·</span>}
        {settled > 0 && <span>{settled} settled</span>}
        {!open && settled === 0 && <span className="truncate">{step?.contract_id ?? ""}</span>}
      </div>
    </div>
  );
}
