/** Keeping a pipeline: the moment a draft stops being one.
 *
 * **This was built server-side in 3E and never wired to the browser.** `POST /pipeline/drafts`,
 * `PUT .../{id}` and `POST .../{id}/keep` have all existed and had no caller — `useGraph`'s 5s
 * idle save takes a `save` callback that nothing passed, so it has never fired in production
 * either. A gate needs an artifact on disk, which is what forced the discovery.
 *
 * **Keep is explicit, and Gate does not do it for you.** A gate certifies what is on disk; if
 * pressing *Gate* silently kept first, it would also silently take on `keep`'s refusal of an
 * illegal graph, and a refusal would arrive dressed as a failed gate. Two buttons, two
 * meanings — the same argument `execution-boundary.md` §3 makes about *Gate* and *Run*.
 */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { post, put } from "../api/client";
import type { DraftGraph, DraftOut, Kept } from "../api/types";

export function useKeep(
  graph: DraftGraph,
  /** A draft this page already owns. **The living session's** — its draft is created with the
   *  session and saved by the server on every commit, so Keep must neither create a second draft
   *  (which the local ref alone would do on first use) nor overwrite the server's graph with the
   *  browser's, which may be carrying an acceptance the server has not confirmed yet. */
  owned: { draftId: string } | null = null,
) {
  const [draftId, setDraftId] = useState<string | null>(owned?.draftId ?? null);
  /** The graph as it was when it was last kept, serialised. **Not a boolean**: `useGraph`'s
   *  `dirty` clears on a successful autosave, and a saved draft is still not a kept one. */
  const [keptGraph, setKeptGraph] = useState<string | null>(null);
  /** **When** it was kept, for the rail's `kept <time>`. The rail's own tests pass a phrase
   *  ("3 minutes ago"), so this field has always been a time — `Builder` handed it the literal
   *  string "kept" instead, and the rail rendered `kept kept`. A wall clock rather than a
   *  relative phrase, because a relative one goes stale in place with nothing to re-render it. */
  const [keptAt, setKeptAt] = useState<string | null>(null);

  const keep = useMutation({
    mutationFn: async () => {
      if (owned !== null) {
        await post<Kept>(`/pipeline/drafts/${owned.draftId}/keep`, {});
        return owned.draftId;
      }
      let id = draftId;
      if (id === null) {
        id = (await post<DraftOut>("/pipeline/drafts", { graph, name: "" })).id;
        setDraftId(id);
      } else {
        await put<DraftOut>(`/pipeline/drafts/${id}`, { graph, name: "" });
      }
      await post<Kept>(`/pipeline/drafts/${id}/keep`, {});
      return id;
    },
    onSuccess: () => {
      setKeptGraph(JSON.stringify(graph));
      setKeptAt(new Date().toLocaleTimeString());
    },
  });

  const moved = keptGraph !== null && keptGraph !== JSON.stringify(graph);

  return {
    // The owned id wins: the session loads after this hook first runs, so state set from it is stale.
    draftId: owned?.draftId ?? draftId,
    keptAt,
    keep: () => keep.mutate(),
    /** The same verb, awaitable — what `useRun` needs to sequence keep -> lint -> sheet.
     *  `mutate` returns void by design; a caller that must know whether the artifact landed
     *  cannot use it, and guessing from `isPending` is how a sequence gets out of order. */
    keepAsync: () => keep.mutateAsync(),
    keeping: keep.isPending,
    /** A coded refusal from `keep` — `MD05xx` for an illegal graph. Shown, not swallowed. */
    error: keep.error ? String(keep.error.message) : null,
    /** Why a gate cannot run yet, or `null`. The reason is the message, so the control can
     *  carry it and a person is never left guessing at a disabled button. */
    blocked:
      keptGraph === null
        ? "Keep this pipeline first — a gate certifies what was kept."
        : moved
          ? "You have changed it since you kept it. Keep again to gate the new version."
          : null,
  };
}
