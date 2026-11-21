import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import { get, post } from "../api/client";
import type { components } from "../api/schema";
import { LivingBuilder } from "../build/living/LivingBuilder";
import { Failed, Loading } from "../ui/States";
import { get as fromWiener } from "../wiener/api/client";
import type { components as wiener } from "../wiener/api/schema";
import { phaseWords } from "../analysis/run/model";
import { useAnalysisRuns } from "../analysis/run/useRuns";
import { analysisAddress } from "./address";
import { AnalysisSlot, type AnalysisPage } from "./rail/AnalysisSlot";
import { RailSlot } from "./rail/RailContext";

type DraftOut = components["schemas"]["DraftOut"];
type AnalysisData = components["schemas"]["AnalysisDataView"];
type DraftsPage = components["schemas"]["DraftsPage"];
type AuthoringSessionView = components["schemas"]["AuthoringSessionView"];
type RunsPage = wiener["schemas"]["RunsPage"];

type Analysis = { draftId: string; name: string };
const AnalysisContext = createContext<Analysis | null>(null);

/** The open analysis, for any page inside `/a/:draft/…`. */
export function useAnalysis(): Analysis {
  const analysis = useContext(AnalysisContext);
  if (!analysis) throw new Error("useAnalysis outside AnalysisFrame");
  return analysis;
}

/** **An analysis is a pipeline draft** (#511, spec "Approaches" 1): its Data, Build and Run live
 *  at `/a/<draft>/…`, and this frame puts it in the rail's slot for every page inside. */
export function AnalysisFrame() {
  const { draft: draftId = "" } = useParams();
  const location = useLocation();
  const draft = useQuery({
    queryKey: ["draft", draftId],
    queryFn: () => get<DraftOut>(`/pipeline/drafts/${encodeURIComponent(draftId)}`),
  });
  // What each page holds, under its name in the rail (the board's status line and counts).
  const data = useQuery({
    queryKey: ["analysis-data", draftId],
    queryFn: () => get<AnalysisData>(`/data/${encodeURIComponent(draftId)}`),
  });
  const kept = (data.data?.samples ?? []).filter((s) => !s.left_out).length;
  // Samples to check, not checks: one odd in two measurements is one (walk 2026-11-16).
  const checks = new Set((data.data?.checks ?? []).map((c) => c.sample)).size;
  const steps = draft.data?.graph.nodes.length ?? 0;
  const latest = useAnalysisRuns(draftId).list[0];
  const status = {
    data: !data.data?.folders.length ? "No data yet"
      : data.data.scan.state === "scanning" ? "Reading…"
      : `${kept} samples${checks ? ` · ${checks} to check` : ""}`,
    build: steps ? `${steps} ${steps === 1 ? "step" : "steps"}` : "Not built",
    run: latest ? `Run ${latest.n} · ${phaseWords(latest.run.phase).toLowerCase()}` : "Not run yet",
  };
  const counts = data.data
    ? { folders: data.data.folders.length, samples: data.data.samples.length, references: data.data.references.length, files: data.data.files }
    : {};
  const after = location.pathname.split("/").slice(3);
  const page: AnalysisPage = after[0] === "build" || after[0] === "run" ? after[0] : "data";
  const run = page === "run" ? after[1] : undefined;

  return (
    <AnalysisContext.Provider value={{ draftId, name: draft.data?.name ?? "" }}>
      <RailSlot><AnalysisSlot draftId={draftId} page={page} run={run} status={status} counts={counts} /></RailSlot>
      {draft.error ? <Failed error={draft.error} /> : <Outlet />}
    </AnalysisContext.Provider>
  );
}

/** The old `/build` addresses, sent to their analysis. `?fake=` stays: it is the static builder
 *  the artboards are compared against, with no server. */
export function LegacyBuild() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>(null);
  const draft = params.get("draft");
  const session = params.get("session");
  const fake = params.get("fake");
  const sent = useRef(false);
  useEffect(() => {
    if (fake || draft || sent.current) return;
    sent.current = true;
    (async () => {
      const id = session
        ? (await get<AuthoringSessionView>(`/pipeline/authoring/${encodeURIComponent(session)}`)).draft_id
        : (await post<{ id: string }>("/pipeline/drafts", { graph: { nodes: [], edges: [] } })).id;
      navigate(analysisAddress(id, "build"), { replace: true });
    })().catch(setError);
  }, [fake, draft, session, navigate]);
  if (fake) return <LivingBuilder />;
  if (draft) return <Navigate to={analysisAddress(draft, "build")} replace />;
  return error ? <Failed error={error} /> : <Loading what="the pipeline" />;
}

/** `/runs/:id`, moved to the analysis whose pipeline it ran: the draft whose digest it carries.
 *  The run shows at once; the move happens when both lists have answered, and never if no draft
 *  ran it (a pipeline uploaded to Wiener by hand). */
export function LegacyRun({ fallback }: { fallback: React.ReactNode }) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  // A run's own view does not carry its digest; its row in the list does.
  const runs = useQuery({
    queryKey: ["runs", "digests"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=1000"),
    retry: false,
  });
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => get<DraftsPage>("/pipeline/drafts") });
  const run = runs.data?.runs?.find((r) => r.id === id);
  // The analysis the run records first: two analyses can share a pipeline, and its digest would
  // pick whichever is listed first (#613). An older run recorded none; its digest still finds one.
  const digest = run?.pipeline_digest;
  const owner = run?.analysis
    ?? (digest ? drafts.data?.drafts?.find((d) => d.digest === digest)?.id : undefined);
  useEffect(() => {
    if (owner) navigate(analysisAddress(owner, "run", encodeURIComponent(id)), { replace: true });
  }, [owner, id, navigate]);
  return <>{fallback}</>;
}

/** `/a/:draft` alone opens its Data. */
export function AnalysisIndex() {
  return <Navigate to="data" replace />;
}
