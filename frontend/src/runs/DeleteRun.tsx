import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { remove } from "../wiener/api/client";

const FINISHED = new Set(["succeeded", "failed", "cancelled", "lost"]);

/** Delete a finished run — **permanent**, so it asks first and says what goes (Part H).
 *
 * Offered only once a run has ended: a live one is cancelled first, and the server refuses it
 * anyway with that sentence. The confirmation points at *Data retention: runs*, where the
 * installation deletes working files on its own.
 */
export function useDeleteRun(runId: string, onDone: () => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => remove(`/api/runs/${runId}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["runs"] });
      onDone();
    },
  });
}

export function DeleteRun({ runId, phase }: { runId: string; phase: string }) {
  const [asking, setAsking] = useState(false);
  const navigate = useNavigate();
  const send = useDeleteRun(runId, () => navigate("/runs"));

  if (!FINISHED.has(phase)) return null;
  if (!asking) {
    return (
      <button type="button" data-testid="delete-run" onClick={() => setAsking(true)}
              className="text-label px-[15px] py-2
                         bg-transparent border border-line text-ink-3 cursor-pointer hover:text-ink">
        delete
      </button>
    );
  }
  return (
    <span data-testid="delete-run-confirm" className="flex flex-wrap items-center gap-2
                                                     text-secondary text-ink-2">
      <span>
        Permanent: its results, its working files and its record go with it. Limits are in{" "}
        <Link to={{ search: "?settings=retention_runs" }} className="text-now-ink">
          Data retention settings
        </Link>.
      </span>
      <button type="button" data-testid="delete-run-yes" disabled={send.isPending}
              onClick={() => send.mutate()}
              className="text-label px-[15px] py-2
                         bg-transparent border cursor-pointer"
              style={{ color: "var(--needs-you-ink)", borderColor: "var(--needs-you)" }}>
        {send.isPending ? "deleting…" : "delete this run"}
      </button>
      <button type="button" onClick={() => setAsking(false)}
              className="bg-transparent border-0 p-0 text-ink-3 cursor-pointer hover:text-ink">
        keep it
      </button>
      {send.error && <span role="alert" className="basis-full"
                           style={{ color: "var(--needs-you-ink)" }}>{send.error.message}</span>}
    </span>
  );
}
