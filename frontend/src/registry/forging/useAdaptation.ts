import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { components } from "../../api/schema";

export type AdaptationView = components["schemas"]["AdaptationView"];
export type ItemView = components["schemas"]["ItemView"];
export type MessageView = components["schemas"]["MessageView"];
export type AdaptationList = components["schemas"]["AdaptationList"];

export const PIECES = ["questions", "contract", "parameters", "vocabulary", "rules"] as const;

/** One adaptation. While the AI works (drafting, or a message waiting for its reply) the page
 *  reads again every two seconds, so the proposals appear when they land. */
export function useAdaptation(id: string) {
  return useQuery({
    queryKey: ["adaptation", id],
    queryFn: () => get<AdaptationView>(`/forge/adaptations/${id}`),
    refetchInterval: (query) => {
      const view = query.state.data;
      const busy = view && (view.phase === "drafting" || view.phase === "asking"
        || view.messages.some((m) => m.pending));
      return busy ? 2_000 : false;
    },
  });
}

export function useAdaptations() {
  return useQuery({
    queryKey: ["adaptations"],
    queryFn: () => get<AdaptationList>("/forge/adaptations"),
  });
}

/** `parameters:param:min_contig` → `min_contig`; `rules:none` → `none needed`. */
export function nameOf(key: string): string {
  const last = key.split(":").at(-1) ?? key;
  return last === "none" ? "none needed" : last;
}
