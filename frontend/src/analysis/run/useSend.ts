/** **Run, with no form** (#508, #511): the kept pipeline from Mendel into Wiener, its inputs answered
 *  from Data.
 *
 * The browser is still the courier between the two services (A179, `wiener.md` §12): it fetches the
 * bundle from Mendel and posts it to Wiener, so neither learns the other exists. What changed is
 * where the parameters come from: `readRunBindings` answers each of the pipeline's inputs from the
 * analysis's samples and references, by type, and the run is sent with exactly those. Nobody types
 * a path. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { blob, get, post } from "../../api/client";
import type { components } from "../../api/schema";
import { post as toWiener, upload } from "../../wiener/api/client";
import type { components as wiener } from "../../wiener/api/schema";

export type Bindings = components["schemas"]["Bindings"];
type ArtifactStored = wiener["schemas"]["ArtifactStored"];
type RunAccepted = wiener["schemas"]["RunAccepted"];

export const bindingsKey = (draftId: string) => ["bindings", draftId];

/** `keep`: whether the pipeline must be kept first (never kept, or changed since). Keeping is
 *  the boundary that validates it and writes `pipeline.yml`; a run is always of a kept one. */
export function useSend(draftId: string, { name = "", keep = false }: { name?: string; keep?: boolean } = {}) {
  const client = useQueryClient();
  const at = encodeURIComponent(draftId);
  const kept = useQuery({
    queryKey: ["keep-for-run", draftId],
    queryFn: async () => { await post(`/pipeline/drafts/${at}/keep`, {}); return true; },
    enabled: keep,
    retry: false,
    staleTime: Infinity,
  });
  const bindings = useQuery({
    queryKey: bindingsKey(draftId),
    queryFn: () => get<Bindings>(`/data/${at}/bindings`),
    enabled: !keep || kept.isSuccess,
  });
  const send = useMutation({
    mutationFn: async () => {
      const answered = await get<Bindings>(`/data/${at}/bindings`);
      if (answered.missing.length) throw new Error(answered.missing.map((m) => m.why).join("; "));
      const archive = await blob(`/pipeline/drafts/${at}/bundle`);
      const stored = await upload<ArtifactStored>("/api/artifacts", "bundle", archive,
                                                  `pipeline-${draftId}.zip`, { ...(name ? { name } : {}), analysis: draftId });
      return await toWiener<RunAccepted>("/api/runs", {
        artifact_id: stored.artifact_id, params: answered.params, executor: "local",
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["runs"] });
      void client.invalidateQueries({ queryKey: ["drafts"] });
    },
  });
  const failed = kept.error ?? bindings.error ?? send.error;
  return {
    bindings: bindings.data ?? null,
    loading: (keep && kept.isPending) || bindings.isPending,
    send: send.mutateAsync,
    sending: send.isPending,
    error: failed ? (failed instanceof Error ? failed.message : String(failed)) : null,
  };
}
