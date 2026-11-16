import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post, put } from "../../api/client";
import type { components } from "../../api/schema";

export type AnalysisData = components["schemas"]["AnalysisDataView"];
export type DataFix = components["schemas"]["Fix"];

const base = (draftId: string) => `/data/${encodeURIComponent(draftId)}`;

/** An analysis's data (#511), read again every 2 s while a scan runs, so the page follows it. */
export function useAnalysisData(draftId: string) {
  const client = useQueryClient();
  const key = ["analysis-data", draftId];
  const data = useQuery({
    queryKey: key,
    queryFn: () => get<AnalysisData>(base(draftId)),
    refetchInterval: (query) => (query.state.data?.scan.state === "scanning" ? 2000 : false),
  });
  const take = (next: AnalysisData) => {
    client.setQueryData(key, next);
    // The facts the pipeline is built from moved with the data.
    void client.invalidateQueries({ queryKey: ["draft", draftId] });
  };
  const tick = useMutation({
    mutationFn: (folders: string[]) => put<AnalysisData>(`${base(draftId)}/folders`, { folders }),
    onSuccess: take,
  });
  const fix = useMutation({
    mutationFn: (change: DataFix) => post<AnalysisData>(`${base(draftId)}/fixes`, change),
    onSuccess: take,
  });
  return {
    data: data.data ?? null,
    loading: data.isPending,
    error: data.error ?? tick.error ?? fix.error ?? null,
    tick: (folders: string[]) => tick.mutate(folders),
    fix: (change: DataFix) => fix.mutate(change),
  };
}
