import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { del, get, post, put } from "../../api/client";
import type { AnalysisData, DataFix } from "./types";

const base = (draftId: string) => `/data/${encodeURIComponent(draftId)}`;

type Method = "put" | "post" | "delete";

/** An analysis's data (#511), read again every 2 s while a scan runs, so the page follows it.
 *
 * - **A reply older than what is shown is ignored**: a poll that left before a change landed
 *   cannot put the page back (Checkpoint C).
 * - **Ticks are shown at once**, so two quick ticks both count.
 * - **When a scan finishes**, the pipeline and the file list are read again: that is when the
 *   facts moved. */
export function useAnalysisData(draftId: string) {
  const client = useQueryClient();
  const key = ["analysis-data", draftId];
  const newest = (next: AnalysisData) => {
    const shown = client.getQueryData<AnalysisData>(key);
    return shown && shown.revision > next.revision ? shown : next;
  };
  const data = useQuery({
    queryKey: key,
    queryFn: async () => newest(await get<AnalysisData>(base(draftId))),
    refetchInterval: (query) => (query.state.data?.scan.state === "scanning" ? 2000 : false),
  });
  const take = async (next: AnalysisData) => {
    await client.cancelQueries({ queryKey: key });
    client.setQueryData(key, newest(next));
  };

  const state = data.data?.scan.state;
  const was = useRef(state);
  useEffect(() => {
    if (was.current === "scanning" && state === "done") {
      void client.invalidateQueries({ queryKey: ["draft", draftId] });
      void client.invalidateQueries({ queryKey: ["analysis-files", draftId] });
    }
    was.current = state;
  }, [state, client, draftId]);

  const tick = useMutation({
    mutationFn: (folders: string[]) => put<AnalysisData>(`${base(draftId)}/folders`, { folders }),
    onMutate: (folders) => {
      const shown = client.getQueryData<AnalysisData>(key);
      if (shown) client.setQueryData(key, { ...shown, folders });
    },
    onSuccess: take,
    onError: () => void client.invalidateQueries({ queryKey: key }),
  });
  const change = useMutation({
    mutationFn: ({ method, path, body }: { method: Method; path: string; body?: unknown }) =>
      method === "put" ? put<AnalysisData>(`${base(draftId)}${path}`, body)
        : method === "post" ? post<AnalysisData>(`${base(draftId)}${path}`, body ?? {})
        : del<AnalysisData>(`${base(draftId)}${path}`),
    onSuccess: take,
  });
  const send = (method: Method, path: string, body?: unknown) => change.mutateAsync({ method, path, body });
  const quietly = (method: Method, path: string, body?: unknown) => void send(method, path, body).catch(() => undefined);

  return {
    data: data.data ?? null,
    loading: data.isPending,
    /** The last refusal, shown on the page whatever was loaded before it. */
    error: tick.error ?? change.error ?? null,
    loadError: data.error ?? null,
    dismiss: () => { tick.reset(); change.reset(); },
    busy: tick.isPending || change.isPending,
    tick: (folders: string[]) => tick.mutate(folders),
    fix: (fix: DataFix) => quietly("post", "/fixes", { kind: fix.kind, sample: fix.sample, file: fix.file,
                                                        measurement: fix.measurement }),
    keepFix: (index: number) => quietly("post", `/fixes/${index}/keep`),
    undoFix: (index: number) => quietly("delete", `/fixes/${index}`),
    setRule: (pattern: string | null) => send("put", "/rule", { pattern }),
    confirmRule: () => quietly("post", "/rule/confirm"),
    rescan: () => quietly("post", "/rescan"),
    addReference: (path: string, typeId: string) => quietly("post", "/references", { path, type_id: typeId }),
    removeReference: (index: number) => quietly("delete", `/references/${index}`),
    addColumn: (name: string) => quietly("put", "/columns", { name, values: {} }),
    setCell: (column: string, sample: string, value: string) =>
      quietly("put", `/columns/${encodeURIComponent(column)}/${encodeURIComponent(sample)}`, { value }),
  };
}
