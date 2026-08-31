import type { components } from "../api/schema";
import { NODE_H, NODE_W, type Point, portOffset } from "./geometry";

type Built = components["schemas"]["BuiltPipeline"];
type Placed = components["schemas"]["PlacedNode"];

const SOCKET_W = 150;
const SOCKET_H = 62;
/** How far from its node a socket sits. Wide enough for the stub to read as a wire. */
const GAP = 90;

/** What this pipeline needs from you and what it is for, drawn on the canvas as **typed
 *  sockets**.
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
 * **The label spec §5 adds does not weaken that.** A person may name a socket, the name lives on
 * the draft, and nothing derived from it reaches a param, a channel or the artifact — see
 * `DraftLabel` in `comeni_core.plan.draft` for the whole of the argument.
 *
 * ═══ WHY IT IS NOT A LAYOUT CHANGE ════════════════════════════════════════════════════════
 *
 * An entry channel is **not a node** — `dag-core` lays out the graph's own nodes, and adding
 * phantom ones would make the canvas and the emitted `.nf` disagree about what a step is. A
 * socket is placed relative to the node it belongs to, client-side, from data already here.
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
/** What this pipeline needs before it can run — **read off `BuiltPipeline.channels`**.
 *
 * ═══ THIS USED TO DERIVE ITS OWN ANSWER, AND THAT WAS THE DEFECT ══════════════════════════
 *
 * `entryChannels()` walked the steps and returned one entry per unwired input **port**: five on
 * the spine, three of them `annotation.gtf`. The resolver deduplicated by type and the emitted
 * workflow had one `params.gtf`. So the run sheet listed three things to bind where the
 * pipeline had one hole, and two of the three answers went nowhere.
 *
 * Spec §0: *the canvas already disagrees with all of this, and that is what made it visible.*
 * Nothing was wrong on screen until somebody tried to name them.
 *
 * The fix is not a better derivation — it is **no derivation**. A channel is a named object in
 * the artifact now, so the browser reads the answer instead of recomputing it. Keeping the old
 * function "for now" is how two derivations of one fact survive, which is the defect this whole
 * plan started from (§12.3).
 *
 * **One reader's rule is still worth stating**, because it moved rather than disappeared: an
 * input that is *unmet* is not an entry channel, it is a hole in the graph. That is the hollow
 * port's job to say, and the resolver already applies it — `_channels` collects ports nothing
 * feeds, and a port with no producer and no channel is what `MD0506` reports.
 */
export function entryChannels(data: Built) {
  return data.channels.map((channel) => ({
    key: channel.name,
    name: channel.name,
    type_id: channel.type_id,
    param: channel.param,
  }));
}

/** The dashed run between a socket and the port it belongs to.
 *
 * **One implementation for both directions**, because the only thing that differs is which edge
 * of the box the line leaves from — and writing it twice is how the input stub and the output
 * stub would come to round their corners differently.
 */
function Stub({ from, to }: { from: Point; to: Point }) {
  const left = Math.min(from.x, to.x);
  const top = Math.min(from.y, to.y);
  const x0 = from.x - left;
  const y0 = from.y - top;
  const x1 = to.x - left;
  const y1 = to.y - top;
  return (
    <svg
      className="absolute overflow-visible"
      style={{ left, top }}
      width={Math.max(1, Math.abs(to.x - from.x))}
      height={Math.max(1, Math.abs(to.y - from.y)) + 1}
    >
      {/* Orthogonal, like every other wire on this canvas — right angles read engineered. */}
      <path
        d={`M${x0},${y0} H${(x0 + x1) / 2} V${y1} H${x1}`}
        fill="none"
        stroke="var(--link)"
        strokeWidth={1}
        strokeDasharray="4 4"
        opacity={0.6}
      />
    </svg>
  );
}

/** One socket box. **INPUT and OUTPUT are the same object seen from two sides**, so they are
 *  one component: same dashes, same blue edge, same absence of anything to type into.
 *
 *  The corner is the tell — an input is rounded on its right, an output on its left, so each
 *  reads as the terminus of a flow that runs left to right (`impl-settled`, phase 6).
 */
function Socket({ kind, port, at, label, onRename, feeds, split, onSplit, onMerge }: {
  kind: "Input" | "Output";
  port: { name: string; type_id: string; states?: string[] };
  at: Point;
  label?: string;
  onRename?: (to: string) => void;
  /** `<node>.<port>` for every port this channel feeds. Empty for an output. */
  feeds?: string[];
  /** Whether a person put this channel here, rather than it being the type's default. */
  split?: boolean;
  onSplit?: (port: string) => void;
  onMerge?: (port: string) => void;
}) {
  return (
    <div
      style={{ left: at.x, top: at.y, width: SOCKET_W, minHeight: SOCKET_H }}
      className={`absolute border border-dashed border-[var(--link)] px-3 py-2
                  bg-[var(--link-soft)] ${kind === "Input" ? "rounded-r" : "rounded-l"}`}
    >
      <span className="block text-label uppercase tracking-[.13em] text-ink-3">{kind}</span>
      {onRename
        ? (
          <input
            // **A LABEL, and the only editable thing on either socket.** It names nothing: the
            // channel name, the param, the samplesheet column and the Nextflow variable are all
            // derived, and this reaches none of them. `test_a_label_reaches_nothing` is the
            // guard, and `norule.test.ts` is why this field is here rather than a path box.
            aria-label={`name for ${port.name}`}
            value={label ?? ""}
            placeholder={port.name}
            onChange={(e) => onRename(e.target.value)}
            // **`pointer-events-auto` against the wrapper's `none`.** A socket does not take the
            // pointer — dragging across one pans the canvas, which is what it did before there
            // was anything to type into. The field is the one exception and says so here rather
            // than by the wrapper giving the whole box back.
            className="block w-full text-body text-ink bg-transparent border-0 p-0
                       pointer-events-auto placeholder:text-ink-3 focus:outline-none"
          />
        )
        : <span className="block text-body text-ink">{port.name}</span>}
      {/* **The TYPE, and there is nothing else to show.** No value, no path, no field —
          the binding happens at the run. */}
      <span className="block font-data text-label text-[var(--link)] truncate">
        {port.type_id}
        {(port.states ?? []).length > 0 && `[${(port.states ?? []).join(", ")}]`}
      </span>

      {/* ═══ SPLIT AND MERGE — spec §4, the operator's "multiple of the same type" ═══════
          **Offered only where there is a choice to make.** A channel feeding one port has
          nothing to split off; a channel feeding three is the interesting case — one shared
          reference annotation, or one per step. Both are legal pipelines and they analyse
          different experiments, so the canvas asks rather than deciding, which is why the
          grouping lives on the draft and not in a derivation.

          A channel a person split shows *merge* instead: the same control in reverse. */}
      {onSplit && (feeds?.length ?? 0) > 1 && (
        <ul className="mt-1 pointer-events-auto list-none p-0 m-0">
          {feeds?.map((key) => (
            <li key={key} className="flex items-center justify-between gap-1">
              <span className="font-data text-label text-ink-3 truncate">{key}</span>
              <button
                onClick={() => onSplit(key)}
                aria-label={`give ${key} its own channel`}
                className="text-label text-[var(--link)] bg-transparent border-0 cursor-pointer
                           px-1 hover:bg-[var(--hover)]"
              >
                split
              </button>
            </li>
          ))}
        </ul>
      )}
      {onMerge && split && feeds?.length === 1 && (
        <button
          onClick={() => onMerge(feeds[0])}
          aria-label={`put ${feeds[0]} back on the shared channel`}
          className="mt-1 pointer-events-auto text-label text-[var(--link)] bg-transparent
                     border-0 cursor-pointer px-1 hover:bg-[var(--hover)]"
        >
          merge
        </button>
      )}
    </div>
  );
}

/** Where a socket goes, given the node it belongs to and which side it is on.
 *
 * ═══ THE GUTTER ARITHMETIC, AND IT RUNS BOTH WAYS ═════════════════════════════════════════
 *
 * A socket needs `SOCKET_W + GAP` = 240px of clear space beside it, and a rank is `RANK_PITCH`
 * = 224px from the one before it. So for an input on any node past rank 0 the space to its left
 * is **already occupied by the node that feeds it**, which is exactly what it looked like:
 * `annotation.gtf` drawn on top of SAMTOOLS_SORT.
 *
 * **The mirror holds for outputs**: a node at the last rank has clear space to its right by
 * construction, and one before it does not.
 *
 * Below is the honest place for the rest. It is beside its node, it overlaps nothing, and the
 * stub becomes a short vertical instead of a long horizontal through a node.
 */
function place(kind: "Input" | "Output", anchor: Point, index: number, clear: boolean) {
  // **The first socket is level with the first port; the rest stack clear of it.** `portOffset`
  // steps by 22, which is right for a 7px port and puts two 62px cards on top of each other —
  // so the BOX stacks by its own height while the WIRE still lands on the port, and the stub
  // between them reconciles the two. That is what a stub is for.
  const stacked = index * (SOCKET_H + 8);
  const box = clear
    ? {
      x: kind === "Input" ? anchor.x - SOCKET_W - GAP : anchor.x + NODE_W + GAP,
      y: anchor.y + portOffset(0) - SOCKET_H / 2 + stacked,
    }
    : {
      x: kind === "Input" ? anchor.x : anchor.x + NODE_W - SOCKET_W,
      y: anchor.y + NODE_H + 20 + stacked,
    };
  // Where the stub meets the box: its near edge, at its middle. Where it meets the node: the
  // port's own offset on the node's edge — the same derivation the wires use, so a socket
  // cannot land 39px from the chevron it points at.
  //
  // **`tip`, not `port`.** The three keys here are spread beside the `PortView` they belong to,
  // and a key called `port` silently replaced it with a coordinate — every socket rendered its
  // kind and nothing else. Caught by the first test written against an output.
  return {
    box,
    edge: { x: kind === "Input" ? box.x + SOCKET_W : box.x, y: box.y + SOCKET_H / 2 },
    tip: {
      x: kind === "Input" ? anchor.x : anchor.x + NODE_W,
      y: anchor.y + portOffset(index),
    },
  };
}

/** Both halves of what a pipeline touches: what it needs, and what it is for.
 *
 * The two are one component because they are one arithmetic seen from two sides — see `place`.
 * Splitting them is how the input gutter and the output gutter would come to disagree.
 */
export function Sources({
  data, offsets, labels, onRename, declared, onSplit, onMerge,
}: {
  data: Built;
  offsets: Record<string, { x: number; y: number }>;
  /** `<node>.<port>` → what a person called it. Draft-only; see `DraftLabel`. */
  labels?: Record<string, string>;
  /** Omitted where the canvas is read-only — the run graph draws sockets and renames none. */
  onRename?: (key: string, to: string) => void;
  /** `<node>.<port>` for every socket a person has given its own channel. The server's
   *  `channels` say what the grouping IS; this says which of it was somebody's decision, which
   *  is the difference between offering *split* and offering *merge*. */
  declared?: string[];
  onSplit?: (port: string) => void;
  onMerge?: (port: string) => void;
}) {
  const consumed = new Set(data.layout.wires.map((w) => `${w.from_node}.${w.from_port}`));
  const at = (node: Placed) => offsets[node.id] ?? { x: node.x, y: node.y };
  const placed = new Map(data.layout.nodes.map((node) => [node.id, node]));
  // **The last rank, not a count.** Ranks need not be contiguous and a node's own `rank` is
  // what this compares against, so the maximum is the only honest reading of "furthest along".
  const last = data.layout.nodes.reduce((n, node) => Math.max(n, node.rank), 0);

  /** Where a port sits on its node's edge, in canvas coordinates. `-1` when the node is not
   *  laid out yet, which is a render between an edit and the server catching up. */
  const tipOf = (key: string, side: "in" | "out") => {
    const [nodeId, portName] = [key.slice(0, key.indexOf(".")), key.slice(key.indexOf(".") + 1)];
    const node = placed.get(nodeId);
    const step = data.steps.find((s) => s.id === nodeId);
    if (!node || !step) return null;
    const index = step.ports.filter((p) => p.side === side).findIndex((p) => p.name === portName);
    if (index < 0) return null;
    const anchor = at(node);
    return {
      node,
      point: {
        x: side === "in" ? anchor.x : anchor.x + NODE_W,
        y: anchor.y + portOffset(index),
      },
    };
  };

  // ═══ ONE SOCKET PER CHANNEL — spec §0 AND §12.3 ═════════════════════════════════════════
  //
  // **This drew one per unwired PORT**, which is what made §0's defect visible: five sockets on
  // the spine, three of them `annotation.gtf`, above an artifact with one `params.gtf`. The
  // channel set is the server's answer now, so a channel feeding three ports is drawn **once**
  // with three stubs — which is a picture that agrees with the emitted workflow rather than one
  // that contradicts it.
  //
  // Anchored to its FIRST consumer, and the gutter arithmetic is unchanged: a socket needs
  // 240px of clear space and only rank 0 has it, so the rest stack below. `index` is now the
  // channel's position among those anchored at that node rather than a port index — the same
  // stacking, counted over the thing actually being drawn.
  const perNode = new Map<string, number>();
  const inputs = data.channels.flatMap((channel) => {
    const first = channel.ports.map((key) => tipOf(key, "in")).find((t) => t !== null);
    // A channel nothing consumes has nowhere to be drawn. It cannot happen in a built
    // pipeline — `_channels` collects the ports that need one — and returning nothing beats
    // inventing a position for it.
    if (!first) return [];
    const index = perNode.get(first.node.id) ?? 0;
    perNode.set(first.node.id, index + 1);
    const kind = "Input" as const;
    const geometry = place(kind, at(first.node), index, first.node.rank === 0);
    return [{
      key: channel.name,
      kind,
      port: { name: channel.name, type_id: channel.type_id, states: channel.states },
      feeds: channel.ports,
      box: geometry.box,
      edge: geometry.edge,
      // **Every port it feeds, not only the one it is anchored to.** A channel drawn once with
      // one line to one of its three consumers would be a different lie from the old one.
      tips: channel.ports
        .map((key) => tipOf(key, "in"))
        .filter((t) => t !== null)
        .map((t) => t.point),
    }];
  });

  // ═══ WHAT THE PIPELINE IS FOR — spec §4.1 ═══════════════════════════════════════════════
  //
  // `materialise.goal_of` has computed exactly this since Plan 3E — `want` is every unwired
  // `produces` — and **the canvas drew none of it.** A terminal `counts.matrix` was an unwired
  // port with nothing marking it as the thing the whole graph exists to produce.
  //
  // **Still derived here, unlike the inputs, and the asymmetry is real rather than an
  // oversight.** A channel is a named object in the artifact because a laboratory binds one; an
  // output is bound by nobody and `Goal.want` is a list of type ids with no identity of its
  // own. When phase 4 gives outputs somewhere to be named, this reads the server's answer too.
  const outputs = data.layout.nodes.flatMap((node) => {
    const step = data.steps.find((s) => s.id === node.id);
    if (!step) return [];
    const anchor = at(node);
    return step.ports
      .filter((p) => p.side === "out")
      .flatMap((port, index) => {
        // Consumed by a step on the canvas? Then it is not what the pipeline is for.
        if (consumed.has(`${node.id}.${port.name}`)) return [];
        const kind = "Output" as const;
        const geometry = place(kind, anchor, index, node.rank === last);
        return [{
          key: `${node.id}.${port.name}`,
          kind,
          port,
          feeds: undefined,
          box: geometry.box,
          edge: geometry.edge,
          tips: [geometry.tip],
        }];
      });
  });

  const sockets = [...inputs, ...outputs];
  if (sockets.length === 0) return null;

  return (
    <>
      {sockets.map((s) => (
        <div
          key={`${s.kind}.${s.key}`}
          data-testid={s.kind === "Input" ? "source" : "terminal"}
          className="absolute pointer-events-none"
        >
          {/* **One stub per port, because a channel may feed several.** Three `annotation.gtf`
              consumers get one socket and three lines — the picture §0 says was missing, where
              five sockets sat above one `params.gtf`. */}
          {s.tips.map((tip, n) => (
            <Stub
              key={n}
              from={s.kind === "Input" ? s.edge : tip}
              to={s.kind === "Input" ? tip : s.edge}
            />
          ))}
          <Socket
            kind={s.kind}
            port={s.port}
            at={s.box}
            label={labels?.[s.key]}
            onRename={onRename && ((to: string) => onRename(s.key, to))}
            feeds={s.kind === "Input" ? s.feeds : undefined}
            split={s.kind === "Input" && (s.feeds ?? []).some((p) => declared?.includes(p))}
            onSplit={s.kind === "Input" ? onSplit : undefined}
            onMerge={s.kind === "Input" ? onMerge : undefined}
          />
        </div>
      ))}
    </>
  );
}
