import type { components } from "../api/schema";
import { NODE_H, NODE_W } from "./geometry";

type Placed = components["schemas"]["PlacedNode"];

/** The whole graph, small, in the canvas's bottom-right corner.
 *
 * **It pays for a deletion.** `impl-settled` is explicit that *the left steps list is deleted on
 * purpose — it duplicated the canvas. Orientation is the minimap's job.* That sentence only
 * holds if the minimap exists, and it did not: the list went in Plan 4 phase 3a and nothing
 * replaced the thing it was good at, which is answering *how much more graph is there, and
 * where is the part that needs me* without panning to find out.
 *
 * ═══ IT IS NOT A CONTROL ══════════════════════════════════════════════════════════════════
 *
 * The artboard draws marks and nothing else — no viewport rectangle, no click-to-jump. Both are
 * obvious additions and both are guesses; a rectangle in particular has to track pan and zoom
 * exactly or it lies about where you are, which is worse than not drawing one. `pointer-events:
 * none` says so structurally rather than by omission.
 *
 * ═══ THE COLOUR IS THE TIER LADDER, UNCHANGED ═════════════════════════════════════════════
 *
 * `impl-inv`: *settled gets NO COLOUR AT ALL. Only measured (amber) and open (red) spend any.*
 * A minimap that coloured every mark would be a second palette competing with the canvas's, and
 * at 15px a mark it would read as confetti. The neutral is `--mark`, which is what the artboard
 * gives the registration marks — the same "structure, not content" grey.
 */
const W = 146;
const H = 58;
const PAD = 8;

const COLOUR: Record<number, string> = {
  3: "var(--measured)",
  4: "var(--undecided)",
};

/** How much room the drawn graph actually takes, in canvas coordinates.
 *
 * **Not `layout.width` / `layout.height`.** Two things sit outside the layout's box: a node
 * somebody has dragged, and the entry-channel sockets, which `Sources` puts *below* any node
 * past rank 0 because a rank is 224px and a socket needs 240px of clear space to its left. So
 * the layout's own height is an underestimate, and *Fit* using it left the bottom of the graph
 * off the screen — the thing it exists to prevent.
 *
 * `SOCKETS` is that overhang: one socket's height plus its gap, added below.
 *
 * **And `GUTTER` is the other one, which was missing.** A rank-0 input socket sits at
 * `x - SOCKET_W - GAP` = 240px left of the node it feeds, and `left` was `min(xs)` — so *Fit*
 * cut the inputs off the left edge in exactly the way it cut the sockets off the bottom. That
 * went unnoticed because nothing was drawn on the right at all; Plan 5B phase 1 puts an OUTPUT
 * socket there and makes the asymmetry visible. Both gutters are added here, unconditionally
 * and for the same reason `SOCKETS` is: a graph with no sockets loses 240px of margin, and a
 * graph with them stays on screen.
 */
const SOCKETS = 96;
const GUTTER = 240;

export function bounds(nodes: Placed[], offsets: Record<string, { x: number; y: number }>) {
  const at = (node: Placed) => offsets[node.id] ?? { x: node.x, y: node.y };
  const xs = nodes.map((n) => at(n).x);
  const ys = nodes.map((n) => at(n).y);
  const left = Math.min(...xs) - GUTTER;
  const top = Math.min(...ys);
  return {
    left,
    top,
    width: Math.max(...xs) + NODE_W + GUTTER - left,
    height: Math.max(...ys) + NODE_H + SOCKETS - top,
  };
}

export function Minimap({
  nodes,
  offsets,
}: {
  nodes: Placed[];
  offsets: Record<string, { x: number; y: number }>;
}) {
  const at = (node: Placed) => offsets[node.id] ?? { x: node.x, y: node.y };
  const { left, top, width, height } = bounds(nodes, offsets);

  // One scale for both axes, so the map is the graph's shape and not a stretched version of it.
  const k = Math.min((W - PAD * 2) / width, (H - PAD * 2) / height);

  return (
    <div
      data-testid="minimap"
      aria-hidden
      style={{ width: W, height: H }}
      className="absolute right-[18px] bottom-[18px] pointer-events-none border border-line
                 bg-[color-mix(in_srgb,var(--paper)_82%,transparent)]"
    >
      {nodes.map((node) => {
        const spot = at(node);
        return (
          <div
            key={node.id}
            data-testid="minimap-mark"
            style={{
              left: PAD + (spot.x - left) * k,
              top: PAD + (spot.y - top) * k,
              width: Math.max(NODE_W * k, 4),
              height: Math.max(NODE_H * k, 3),
              borderColor: COLOUR[node.tier] ?? "var(--mark)",
            }}
            className="absolute border"
          />
        );
      })}
    </div>
  );
}
