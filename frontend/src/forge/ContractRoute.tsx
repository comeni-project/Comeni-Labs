import { useParams } from "react-router";

import { Drift } from "./Drift";
import { Module } from "./Module";

/** One splat, two screens.
 *
 * `/forge/contracts/*` is a splat because a contract id contains slashes, and that is also
 * why `:id/drift` cannot be a second pattern — react-router has no splat-in-the-middle. So
 * one component owns the splat and reads the last segment.
 *
 * A contract id is `namespace/tool@version` and never ends in `/drift`, so that segment is
 * unambiguous. It is a property of `ContractId` rather than a convenience: if ids ever gain a
 * path suffix this breaks here, loudly, rather than in a fetch nobody is watching.
 */
export function ContractRoute() {
  const rest = useParams()["*"] ?? "";
  const suffix = "/drift";
  return rest.endsWith(suffix) ? (
    <Drift id={rest.slice(0, -suffix.length)} />
  ) : (
    <Module id={rest} />
  );
}
