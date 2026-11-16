import { useQuery } from "@tanstack/react-query";

import { get, post } from "../../api/client";
import type { components } from "../../api/schema";
import type { AuthoringSession } from "../../api/types";
import type { AnalysisData } from "../data/types";
import { get as fromWiener } from "../../wiener/api/client";
import type { components as wiener } from "../../wiener/api/schema";
import { numbered, TERMINAL, type ProcessRow, type RunNode, type StepFacts } from "./model";

type DraftsPage = components["schemas"]["DraftsPage"];
type RunsPage = wiener["schemas"]["RunsPage"];

/** **Runs of this analysis**: the runs of the pipeline it keeps, matched by digest, newest first.
 *  The same query key as `LegacyRun`, so one request answers both. */
export function useAnalysisRuns(draftId: string) {
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => get<DraftsPage>("/pipeline/drafts") });
  const runs = useQuery({
    queryKey: ["runs", "digests"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=1000"),
    refetchInterval: 5_000,
    retry: false,
  });
  const row = drafts.data?.drafts?.find((d) => d.id === draftId);
  const list = numbered(runs.data?.runs ?? [], row?.digest);
  return {
    list,
    row,
    loading: drafts.isPending || (runs.isPending && !runs.isError),
    error: runs.error,
    live: list.some(({ run }) => !TERMINAL.has(run.phase)),
  };
}

/** The analysis's pipeline as Build draws it — its steps, inputs and where each sits — so Run's
 *  graph is Build's canvas with the run drawn on it. Opens the draft's one conversation, as Build. */
export function useBuildCanvas(draftId: string) {
  return useQuery({
    queryKey: ["run-canvas", draftId],
    queryFn: async () => {
      const { session_id } = await post<{ session_id: string }>(
        `/pipeline/drafts/${encodeURIComponent(draftId)}/session`, {});
      return await get<AuthoringSession>(`/pipeline/authoring/${session_id}`);
    },
    staleTime: 60_000,
  });
}

/** What Run needs of each step from Build, by step id. */
export function factsOf(session: AuthoringSession | undefined): Record<string, StepFacts> {
  const steps = session?.canvas?.steps ?? [];
  return Object.fromEntries(steps.map((s) => [s.id, {
    does: (s as { does?: string | null }).does,
    perSample: s.runs === "per_item",
    gathers: s.ports.some((p) => p.side === "in" && (p as { gathers?: boolean }).gathers),
  }]));
}

/** One run's record, read again while it is live. */
export function useRun(runId: string) {
  const state = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fromWiener<RunState>(`/api/runs/${runId}`),
    refetchInterval: (q) => (q.state.data && TERMINAL.has(q.state.data.phase) ? false : 4_000),
  });
  const live = !state.data || !TERMINAL.has(state.data.phase);
  const overview = useQuery({
    queryKey: ["overview", runId],
    queryFn: () => fromWiener<{ rows: ProcessRow[] }>(`/api/runs/${runId}/overview`),
    refetchInterval: live ? 4_000 : false,
  });
  const graph = useQuery({
    queryKey: ["run-graph", runId],
    queryFn: () => fromWiener<{ nodes: RunNode[] }>(`/api/runs/${runId}/graph`),
    refetchInterval: live ? 4_000 : false,
  });
  return { state, overview, graph, live };
}

export type RunState = {
  run_id: string;
  phase: string;
  counts: { succeeded: number; failed: number; cached: number; running: number; submitted: number };
  started_at_ms: number | null;
  ended_at_ms: number | null;
  executor?: string;
  name?: string;
  work_cleared?: boolean;
  last_activity_ms?: number | null;
};

/** Kept samples of the analysis: the denominator of *14 of 24 samples finished*. */
export function useSamples(draftId: string): string[] {
  const data = useQuery({
    queryKey: ["analysis-data", draftId],
    queryFn: () => get<AnalysisData>(`/data/${encodeURIComponent(draftId)}`),
  });
  return (data.data?.samples ?? []).filter((s) => !s.left_out).map((s) => s.name);
}

/** What Data answers each input type with: a reference's file name, by type. */
export function useReferences(draftId: string): Record<string, string> {
  const data = useQuery({
    queryKey: ["analysis-data", draftId],
    queryFn: () => get<AnalysisData>(`/data/${encodeURIComponent(draftId)}`),
  });
  return Object.fromEntries((data.data?.references ?? []).map((r) => [r.type_id, r.name]));
}
