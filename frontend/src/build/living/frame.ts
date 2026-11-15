import type { components } from "../../api/schema";
import type { AuthoringSession, Step } from "../../api/types";

export type Frame = components["schemas"]["CanvasFrame"];
type Channel = components["schemas"]["ChannelView"];

/** A frame for a session with no server behind it — the fixtures — made the way the server makes
 *  one: the draft, with metadata only for what is drawn.
 *  **So a fixture exercises the same renderer as a live session**, never a label-only stand-in. */
export function fixtureFrame(
  session: AuthoringSession, steps: Record<string, Step>, channels: Channel[],
): Frame {
  const graph = session.graph;
  const drawn = new Set(graph.nodes.map((n) => n.id));
  return {
    context: { draft_revision: session.revision, decision_revision: 0,
               session_version: session.row_version ?? 0, registry: "fixture" },
    current: session.projection_current !== false,
    graph,
    steps: Object.values(steps).filter((s) => drawn.has(s.id)),
    channels: channels.filter((c) => c.ports.some((p) => drawn.has(p.split(".")[0]))),
    placement: Object.fromEntries(Object.entries(session.placement ?? {})
      .filter(([id]) => drawn.has(id))) as Frame["placement"],
  };
}

/** The same session, carrying a fixture frame for its own graph. */
export const framed = (
  session: AuthoringSession, steps: Record<string, Step>, channels: Channel[] = [],
): AuthoringSession => ({ ...session, canvas: fixtureFrame(session, steps, channels) });
