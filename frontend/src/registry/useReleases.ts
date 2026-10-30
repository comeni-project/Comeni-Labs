import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post } from "../api/client";
import type { components } from "../api/schema";

export type ReleasesPage = components["schemas"]["ReleasesPage"];

/** What is unreleased and what has been cut. While a release is being cut, reads again. */
export function useReleases() {
  return useQuery({
    queryKey: ["releases"],
    queryFn: () => get<ReleasesPage>("/forge/releases"),
    refetchInterval: (query) =>
      query.state.data?.recent.some((r) => r.state === "cutting") ? 3_000 : false,
  });
}

export function useCutRelease() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { version: string; notes: string }) =>
      post<ReleasesPage>("/forge/releases", input),
    onSuccess: (page) => client.setQueryData(["releases"], page),
    onError: () => client.invalidateQueries({ queryKey: ["releases"] }),
  });
}
