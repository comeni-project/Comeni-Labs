import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

/** **Both types come from the schema rather than from here.**
 *
 * `make client` regenerates them from the API's own OpenAPI document, so a field the backend
 * renames is a compile error rather than a runtime `undefined`. Re-declaring them by hand —
 * which is what this file first did — is the one edit that makes generating them pointless.
 */
export type AnswerInput = components["schemas"]["AnswerRequest"];
export type Answered = components["schemas"]["Answered"];

/** The mutation shape every write in this app follows.
 *
 * **Invalidate, never hand-patch.** An answer changes the draft's `remaining` and the queue's
 * aggregation; recomputing that in the client is a second implementation of `aggregate()`
 * and the two would drift the first time the grouping key changes.
 */
export function useAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AnswerInput) => post<Answered>("/questions/answer", input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["questions"] });
      client.invalidateQueries({ queryKey: ["health"] });
    },
  });
}
