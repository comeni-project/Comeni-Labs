import type { components } from "../api/schema";
import { NODE_H, portOffset } from "./geometry";

type Built = components["schemas"]["BuiltPipeline"];
type Placed = components["schemas"]["PlacedNode"];

const SOCKET_W = 150;
const SOCKET_H = 62;
/** How far left of its consumer a socket sits. Wide enough for the stub to read as a wire. */
const GAP = 90;

/** What this pipeline needs from you, drawn on the canvas as **typed sockets**.
 *
 * ═══ INVARIANT 15 DECIDES THIS DESIGN ═════════════════════════════════════════════════════
 *
 * `impl-inv`: *No input accepts a sample identifier, filename or path. The `Goal` holds a
 * SHAPE.* So:
 *
 *   → a source node carries a **TYPE** and never a path
 *   → the **binding** lives with the RUN, not the pipeline
 *   → same pipeline, different data, no edit
 *
 * *If a path ever reaches `pipeline.yml`, the product's central promise is gone. This is not a
 * style choice.* These sockets are deliberately **not editable** — there is nothing to type into
 * them, which is the design saying the invariant out loud. `norule.test.ts` holds the other half:
 * no control in `build/` takes a path except the run sheet, which is Wiener's.
 *
 * ═══ WHY IT IS NOT A LAYOUT CHANGE ════════════════════════════════════════════════════════
 *
 * An entry channel is **not a node** — `dag-core` lays out the graph's own nodes, and adding
 * phantom ones would make the canvas and the emitted `.nf` disagree about what a step is. A
 * socket is placed relative to the consumer it feeds, client-side, from data already here.
 *
 * **Which inputs are entry-fed is derived, not asked for.** An input is fed from outside when it
 * is `met` and no wire targets it — a question about edges, not about types, so deriving it here
 * duplicates no rule. (`useCompatibility.ts`'s warning is about type signatures; this counts
 * arrows.)
 *
 * ═══ WHAT IT REPLACED ═════════════════════════════════════════════════════════════════════
 *
 * Nothing, visibly — which was the defect. An entry channel drew a **wire stub running off to
 * the left with a clipped label and no terminus**, so the canvas said *something feeds this* and
 * never what. A person could only learn what the pipeline required by pressing Run and reading
 * the sheet.
 */
/** What this pipeline needs before it can run: every input port nothing on the canvas feeds.
 *
 * **One derivation, two readers.** The canvas draws these as `INPUT` sockets; the run sheet
 * lists them as the things a person has to bind. Deriving it twice is how the two would come to
 * disagree about what a pipeline needs — and the rule is subtle enough to be worth stating once:
 * an input that is *unmet* is not an entry channel, it is a hole in the graph, and saying so is
 * the hollow port's job.
 */
export function entryChannels(data: Built) {
  const wired = new Set(data.layout.wires.map((w) => `${w.to_node}.${w.to_port}`));
  return data.steps.flatMap((step) =>
    step.ports
      .filter((port) => port.side === "in" && port.met && !wired.has(`${step.id}.${port.name}`))
      .map((port) => ({ key: `${step.id}.${port.name}`, name: port.name, type_id: port.type_id })),
  );
}

export function Sources({ data, offsets }: {
  data: Built;
  offsets: Record<string, { x: number; y: number }>;
}) {
  const wired = new Set(data.layout.wires.map((w) => `${w.to_node}.${w.to_port}`));
  const at = (node: Placed) => offsets[node.id] ?? { x: node.x, y: node.y };

  const sockets = data.layout.nodes.flatMap((node) => {
    const step = data.steps.find((s) => s.id === node.id);
    if (!step) return [];
    const ins = step.ports.filter((p) => p.side === "in");
    return ins.flatMap((port, index) => {
      // Fed by a wire? Then it has a source on the canvas already.
      if (wired.has(`${node.id}.${port.name}`)) return [];
      // Unmet is the hollow port's job to say — an absent input is not an entry channel.
      if (!port.met) return [];
      const anchor = at(node);
      return [{
        key: `${node.id}.${port.name}`,
        port,
        // **Left of a root, below anything else** — and the arithmetic says why rather than a
        // preference. A socket needs `SOCKET_W + GAP` = 240px of clear space to its left, and a
        // rank is `RANK_PITCH` = 224px from the one before it. So for any node past rank 0 the
        // space to its left is *already occupied by the node that feeds it*, which is exactly
        // what it looked like: `annotation.gtf` drawn on top of SAMTOOLS_SORT.
        //
        // Below is the honest place for those. It is beside its consumer, it overlaps nothing,
        // and the stub becomes a short vertical instead of a long horizontal through a node.
        ...(node.rank === 0
          ? {
            // **The first socket is level with the first port; the rest stack clear of it.**
            // `portOffset` steps by 22, which is right for a 7px port and puts two 62px cards
            // on top of each other — so the BOX stacks by its own height while the WIRE still
            // lands on the port, and the stub between them reconciles the two. That is what a
            // stub is for.
            x: anchor.x - SOCKET_W - GAP,
            y: anchor.y + portOffset(0) - SOCKET_H / 2 + index * (SOCKET_H + 8),
            fromY: anchor.y + portOffset(0) + index * (SOCKET_H + 8),
          }
          : {
            x: anchor.x,
            y: anchor.y + NODE_H + 20 + index * (SOCKET_H + 8),
            fromY: anchor.y + NODE_H + 20 + index * (SOCKET_H + 8) + SOCKET_H / 2,
          }),
        // Where the stub meets the consumer: the same derivation the wires use, so a socket
        // cannot land 39px from the chevron it points at. **Left to right**, so an entry
        // channel enters the consumer's LEFT edge at that port's own offset.
        toX: anchor.x,
        toY: anchor.y + portOffset(index),
      }];
    });
  });

  if (sockets.length === 0) return null;

  return (
    <>
      {sockets.map((s) => (
        <div key={s.key} data-testid="source" className="absolute pointer-events-none">
          <svg
            className="absolute overflow-visible"
            style={{ left: s.x + SOCKET_W, top: Math.min(s.fromY, s.toY) }}
            width={Math.max(1, s.toX - s.x - SOCKET_W)}
            height={Math.max(1, Math.abs(s.toY - s.fromY)) + 1}
          >
            {/* Orthogonal, like every other wire on this canvas — right angles read engineered. */}
            <path
              d={`M0,${s.fromY - Math.min(s.fromY, s.toY)}
                  H${(s.toX - s.x - SOCKET_W) / 2}
                  V${s.toY - Math.min(s.fromY, s.toY)}
                  H${s.toX - s.x - SOCKET_W}`}
              fill="none"
              stroke="var(--link)"
              strokeWidth={1}
              strokeDasharray="4 4"
              opacity={0.6}
            />
          </svg>

          <div
            style={{ left: s.x, top: s.y, width: SOCKET_W, minHeight: SOCKET_H }}
            className="absolute border border-dashed border-[var(--link)] rounded-r px-3 py-2
                       bg-[var(--link-soft)]"
          >
            <span className="block text-label uppercase tracking-[.13em] text-ink-3">Input</span>
            <span className="block text-body text-ink">{s.port.name}</span>
            {/* **The TYPE, and there is nothing else to show.** No value, no path, no field —
                the binding happens at the run. */}
            <span className="block font-data text-label text-[var(--link)] truncate">
              {s.port.type_id}
              {(s.port.states ?? []).length > 0 && `[${(s.port.states ?? []).join(", ")}]`}
            </span>
          </div>
        </div>
      ))}
    </>
  );
}
