import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

export type ProposeInput = components["schemas"]["ProposeRequest"];
export type Proposed = components["schemas"]["Proposed"];

/** Declining a question. The hole stays open, so the queue is invalidated rather than the row
 *  being removed — `still_open` is the payload saying so. */
export function usePropose() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: ProposeInput) => post<Proposed>("/questions/propose", input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}
