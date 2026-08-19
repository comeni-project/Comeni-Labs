import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

export type DraftBody = components["schemas"]["DraftBody"];
export type DraftResult = components["schemas"]["DraftResult"];

/** Start a draft from a source.
 *
 * **The body carries no paths**, and that is the phase's whole constraint: `settings` owns where
 * the registry, the source and the workspace live. `DraftBody` is `extra="forbid"` on the server,
 * so a convenience parameter added here would be a 422 rather than a quiet second answer.
 *
 * Two invalidations: a new draft is both a row that changed state and work in the queue.
 */
export function useDraft() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: DraftBody) => post<DraftResult>("/sources/draft", body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["sources"] });
      client.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}
