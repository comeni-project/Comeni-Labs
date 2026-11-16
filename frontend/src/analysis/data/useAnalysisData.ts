import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, get, post, put } from "../../api/client";
import type { AnalysisData, DataFix } from "./types";

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
  const change = useMutation({
    mutationFn: ({ method, path, body }: { method: "put" | "post" | "delete"; path: string; body?: unknown }) =>
      method === "put" ? put<AnalysisData>(`${base(draftId)}${path}`, body)
        : method === "post" ? post<AnalysisData>(`${base(draftId)}${path}`, body ?? {})
        : del<AnalysisData>(`${base(draftId)}${path}`),
    onSuccess: take,
  });
  const send = (method: "put" | "post" | "delete", path: string, body?: unknown) =>
    change.mutate({ method, path, body });
  return {
    data: data.data ?? null,
    loading: data.isPending,
    error: data.error ?? tick.error ?? fix.error ?? change.error ?? null,
    tick: (folders: string[]) => tick.mutate(folders),
    fix: (change: DataFix) => fix.mutate(change),
    setRule: (pattern: string | null) => send("put", "/rule", { pattern }),
    confirmRule: () => send("post", "/rule/confirm"),
    undoFix: (index: number) => send("delete", `/fixes/${index}`),
    addReference: (path: string, typeId: string) => send("post", "/references", { path, type_id: typeId }),
    removeReference: (index: number) => send("delete", `/references/${index}`),
    setColumn: (name: string, values: Record<string, string>) => send("put", "/columns", { name, values }),
  };
}
