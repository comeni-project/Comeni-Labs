import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post } from "../api/client";
import type { components } from "../api/schema";

export type ProposalsView = components["schemas"]["ProposalsView"];
export type ProposalView = components["schemas"]["ProposalView"];
export type InUseView = components["schemas"]["InUseView"];

const KEY = ["rule-proposals"];

/** What the model proposed from people's answers, and what is in use. Reads again while a
 *  Propose is running. */
export function useLearnedRules() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => get<ProposalsView>("/rules/proposals"),
    refetchInterval: (query) => (query.state.data?.running ? 3_000 : false),
  });
}

/** One verb on the page: each answers with the whole page, as it now stands. */
export function useRuleVerb() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => post<ProposalsView>(path, {}),
    onSuccess: (page) => client.setQueryData(KEY, page),
    onError: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
