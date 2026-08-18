import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "./client";
import type { components } from "./schema";

export type DecideInput = components["schemas"]["DecideRequest"];
export type Decided = components["schemas"]["Decided"];

/** Approving or rejecting a proposal. One mutation, because they are one decision. */
export function useDecide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: DecideInput) => post<Decided>("/questions/proposals/decide", input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}
