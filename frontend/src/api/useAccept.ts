import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

export type AcceptBody = components["schemas"]["AcceptBody"];
export type AcceptResult = components["schemas"]["AcceptResult"];

/** Take the source's value for one field.
 *
 * **Four invalidations, because accepting changes the registry itself** rather than a draft:
 * this contract's drift, the contracts list's status counts, the queue's drift rows, and the
 * health strip. Invalidate, never hand-patch — recomputing which of those a commit moved is
 * a second implementation of `ops.check`.
 */
export function useAccept(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AcceptBody) => post<AcceptResult>(`/contracts/${id}/drift/accept`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["drift", id] });
      client.invalidateQueries({ queryKey: ["contracts"] });
      client.invalidateQueries({ queryKey: ["questions"] });
      client.invalidateQueries({ queryKey: ["health"] });
    },
  });
}
