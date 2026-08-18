import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

export type AnswerAllInput = components["schemas"]["AnswerAllRequest"];
export type AnsweredAll = components["schemas"]["AnsweredAll"];

/** The batch. Same shape as `useAnswer`, and it invalidates rather than patching for the same
 *  reason: recomputing the queue's aggregation client-side is a second `aggregate()`. */
export function useAnswerAll() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AnswerAllInput) => post<AnsweredAll>("/questions/answer-all", input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}
