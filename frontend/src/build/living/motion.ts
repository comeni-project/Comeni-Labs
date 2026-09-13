import type { MotionEvent, MotionKind } from "./authoringReducer";

/** Which CSS class a domain event puts on which object. **The whole motion policy, in one table.**
 *
 * §1.11: motion follows domain events — a proposal shown, a proposal accepted, a wire committed —
 * and never a fetch completing or a model token arriving. So the canvas does not decide when to
 * animate; it asks this for the class an unplayed event gives an object, plays it, and reports it
 * played. Reduced motion is CSS (`main.css`): the class is still applied and the animation is
 * `none`, so the end state is exactly the same and nothing travels.
 */

export const MOTION: Record<MotionKind, string | null> = {
  proposal_shown: "living-pop",
  proposal_accepted: "living-settle",
  edge_committed: "living-draw",
  // Not drawn on the canvas: a parameter's change is shown where the value is read (the YAML
  // preview, Task 13), and a rejection removes the ghost — withdrawing it, not animating it away,
  // because a leaving animation keeps a step on the canvas the server has already let go of.
  parameter_committed: null,
  proposal_rejected: null,
  validation_changed: null,
};

/** The subject an `edge_committed` event names, for one wire. The reducer spells it the same way. */
export const wireSubject = (edge: { from_node: string; from_port: string; to_node: string }) =>
  `${edge.from_node}.${edge.from_port}->${edge.to_node}`;

/** The unplayed event, if any, that animates this object — and the class it asks for. */
export function motionFor(
  events: MotionEvent[],
  kinds: MotionKind[],
  subject: string,
): { event: MotionEvent; className: string } | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    const className = MOTION[event.kind];
    if (className && kinds.includes(event.kind) && event.subject === subject) {
      return { event, className };
    }
  }
  return null;
}
