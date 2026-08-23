import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { Compatibility } from "../api/types";


/** Whether a wire may be drawn, and whether it is the conventional thing to draw.
 *
 * - `yes` — legal, and the form the target conventionally wants
 * - `conventional-no` — legal, and not that form. `MD0507` will say so on drop.
 * - `no` — illegal, or a port this index has never heard of
 */
export type Verdict = "yes" | "conventional-no" | "no";

/** **A lookup, never a comparison.**
 *
 * The server computed what satisfies what — `mendel_resolver.compatibility.index`, walking the
 * same `InputPort.alternatives()` that `validate` walks, held to it by a test over every port
 * pair in the registry. This intersects two lists it was handed.
 *
 * If a line here ever parses a signature — splits on `[`, compares type ids, subtracts state
 * sets — the rule that decides whether a BAM can feed featureCounts lives in two places, and
 * the second one is invisible to the agreement test. That is the drift this repository has paid
 * for twice: the tier vocabulary hardcoded in a React file, the `Standing` union declared in
 * two places. A test asserts the absence.
 *
 * The **order** of `requires` carries the conventional/structural distinction, and it comes from
 * the contract author's own `alternatives()` — index 0 is the conventional form.
 */
export function accepts(index: Compatibility, sourceKey: string, targetKey: string): Verdict {
  const emitted = index.emits[sourceKey];
  const accepted = index.requires[targetKey];
  if (emitted === undefined || accepted === undefined) return "no";

  const satisfied = index.satisfies[emitted];
  if (satisfied === undefined) return "no";

  const matched = accepted.findIndex((requirement) => satisfied.includes(requirement));
  if (matched < 0) return "no";
  return matched === 0 ? "yes" : "conventional-no";
}

/** The index, fetched once and revalidated cheaply.
 *
 * A long `staleTime` because the ETag makes a revalidation a 304 — the cost of being wrong
 * about staleness is one small request, and the server's cache key and this one are the same
 * registry digest.
 */
export function useCompatibility() {
  return useQuery({
    queryKey: ["compatibility"],
    queryFn: () => get("/pipeline/compatibility"),
    staleTime: 5 * 60 * 1000,
  });
}
