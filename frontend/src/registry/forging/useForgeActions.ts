import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "../../api/client";
import type { components } from "../../api/schema";
import type { AdaptationView } from "./useAdaptation";

type Move = components["schemas"]["Move"];
export type AssemblyView = components["schemas"]["AssemblyView"];

export interface CommandInput {
  move: Move;
  item: string;
  expected?: number;
  value?: unknown;
  because?: string;
}

/** A person's moves on one adaptation. Every mutation re-reads the adaptation; a coded
 *  refusal (`MF0506: … changed since you looked`) is each mutation's `error`. */
export function useForgeActions(id: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["adaptation", id] });
  const command = useMutation({
    mutationFn: (input: CommandInput) =>
      post<AdaptationView>(`/forge/adaptations/${id}/commands`, input),
    onSuccess: (view) => client.setQueryData(["adaptation", id], view),
  });
  const draft = useMutation({
    mutationFn: (piece: string) => post(`/forge/adaptations/${id}/draft`, { piece }),
    onSuccess: refresh,
  });
  const say = useMutation({
    mutationFn: (input: { content: string; item: string | null }) =>
      post(`/forge/adaptations/${id}/messages`, input),
    onSuccess: refresh,
  });
  const assemble = useMutation({
    mutationFn: () => post<AssemblyView>(`/forge/adaptations/${id}/assemble`, {}),
    onSuccess: refresh,
  });
  return { command, draft, say, assemble };
}

/** Starting a forge from the catalogue. */
export function useStartForge() {
  return useMutation({
    mutationFn: (input: { source: string; path: string; reforge?: string | null }) =>
      post<AdaptationView>("/forge/adaptations", input),
  });
}
