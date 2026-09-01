import type { components } from "../api/schema";
import { NODE_H, NODE_W, portOffset } from "./geometry";

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

/** What this pipeline produces: every output port nothing on the canvas consumes.
 *
 * **The same arithmetic as `entryChannels`, read the other way**, and it is deliberately the
 * same shape: this is exactly what `materialise.goal_of` computes as the goal's `want` — *what
 * nothing downstream consumes* — so the canvas and the resolver answer one question once.
 *
 * **Nothing drew these.** `want` has always been computed and there was no output node on the
 * builder at all, so a terminal `counts.matrix` was an unwired port like any other and the
 * drawing never said which port was the thing the pipeline is *for*.
 *
 * **No `met` filter, unlike the input side.** An unmet *input* is a hole in the graph and the
 * hollow port says so; an output has nothing to be unmet about — it is produced or the step is
 * not there.
 */
export function terminalOutputs(data: Built) {
  const consumed = new Set(data.layout.wires.map((w) => `${w.from_node}.${w.from_port}`));
  return data.steps.flatMap((step) =>
    step.ports
      .filter((port) => port.side === "out" && !consumed.has(`${step.id}.${port.name}`))
      .map((port) => ({ key: `${step.id}.${port.name}`, name: port.name, type_id: port.type_id })),
  );
}

export function Sources({ data, offsets, labels, onRename }: {
  data: Built;
  offsets: Record<string, { x: number; y: number }>;
  /** `<node>.<port>` -> what a person called it. Draft-only; it reaches no artifact. */
  labels?: Record<string, string>;
  onRename?: (key: string, label: string) => void;
}) {
  const wired = new Set(data.layout.wires.map((w) => `${w.to_node}.${w.to_port}`));
  const consumed = new Set(data.layout.wires.map((w) => `${w.from_node}.${w.from_port}`));
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

  // **The mirror, and the arithmetic is simpler because the space is free.** An input socket
  // has to dodge the node that feeds its consumer (see above); an output sits to the RIGHT of a
  // terminal node, and a node with an unconsumed output has nothing to its right by
  // construction — that is what makes it terminal.
  const outputs = data.layout.nodes.flatMap((node) => {
    const step = data.steps.find((s) => s.id === node.id);
    if (!step) return [];
    const outs = step.ports.filter((p) => p.side === "out");
    return outs.flatMap((port, index) => {
      if (consumed.has(`${node.id}.${port.name}`)) return [];
      const anchor = at(node);
      return [{
        key: `${node.id}.${port.name}`,
        port,
        x: anchor.x + NODE_W + GAP,
        y: anchor.y + portOffset(0) - SOCKET_H / 2 + index * (SOCKET_H + 8),
        toY: anchor.y + portOffset(0) + index * (SOCKET_H + 8),
        fromX: anchor.x + NODE_W,
        fromY: anchor.y + portOffset(index),
      }];
    });
  });

  if (sockets.length === 0 && outputs.length === 0) return null;

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
            <Name
              at={s.key}
              fallback={s.port.name}
              labels={labels}
              onRename={onRename}
            />
            {/* **The TYPE, and there is nothing else to show.** No value, no path, no field —
                the binding happens at the run. */}
            <span className="block font-data text-label text-[var(--link)] truncate">
              {s.port.type_id}
              {(s.port.states ?? []).length > 0 && `[${(s.port.states ?? []).join(", ")}]`}
            </span>
          </div>
        </div>
      ))}

      {outputs.map((s) => (
        <div key={s.key} data-testid="output" className="absolute pointer-events-none">
          <svg
            className="absolute overflow-visible"
            style={{ left: s.fromX, top: Math.min(s.fromY, s.toY) }}
            width={Math.max(1, s.x - s.fromX)}
            height={Math.max(1, Math.abs(s.toY - s.fromY)) + 1}
          >
            <path
              d={`M0,${s.fromY - Math.min(s.fromY, s.toY)}
                  H${(s.x - s.fromX) / 2}
                  V${s.toY - Math.min(s.fromY, s.toY)}
                  H${s.x - s.fromX}`}
              fill="none"
              stroke="var(--link)"
              strokeWidth={1}
              strokeDasharray="4 4"
              opacity={0.6}
            />
          </svg>

          {/* **Rounded on the LEFT**, where the input socket is rounded on the right — the two
              read as the open ends of the pipeline rather than as two of the same thing. */}
          <div
            style={{ left: s.x, top: s.y, width: SOCKET_W, minHeight: SOCKET_H }}
            className="absolute border border-dashed border-[var(--link)] rounded-l px-3 py-2
                       bg-[var(--link-soft)]"
          >
            <span className="block text-label uppercase tracking-[.13em] text-ink-3">Output</span>
            <Name at={s.key} fallback={s.port.name} labels={labels} onRename={onRename} />
            {/* The type, and there is nothing else to show: where the results go is a RUN
                question, answered on the run sheet by Wiener. */}
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

/** What a person calls a socket, editable in place, falling back to the port's own name.
 *
 * **A label and never a key.** It does not become a `params.<name>`, it does not reach
 * `pipeline.yml`, and no resolver sees it — `tests/test_draft_labels.py` holds that, watched
 * failing against a version that threads it into the channel name. It exists because a pipeline
 * can legitimately take two `fastq.reads`, and *tumour* and *normal* is the difference between a
 * drawing a person can read and one they cannot.
 *
 * `pointer-events-auto` because the sockets are drawn inside a `pointer-events-none` layer —
 * the wires and cards must not eat canvas drags, and this one control must.
 */
function Name({ at, fallback, labels, onRename }: {
  at: string;
  fallback: string;
  labels?: Record<string, string>;
  onRename?: (key: string, label: string) => void;
}) {
  const named = labels?.[at];
  if (!onRename) {
    return <span className="block text-body text-ink">{named || fallback}</span>;
  }
  return (
    <input
      data-testid="socket-name"
      aria-label={`name for ${fallback}`}
      value={named ?? ""}
      placeholder={fallback}
      onChange={(e) => onRename(at, e.target.value)}
      onPointerDown={(e) => e.stopPropagation()}
      className="block w-full bg-transparent border-0 p-0 text-body text-ink outline-none
                 pointer-events-auto placeholder:text-ink-3
                 focus:underline focus:decoration-dotted"
    />
  );
}
