import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { post } from "../wiener/api/client";

/** Stop a run — **the first thing in Wiener that changes anything**, Plan 6 phase 1.
 *
 * The artboard has drawn this button since 2026-08-29 and it was deliberately not built: there
 * was no cancel endpoint, and a control that goes nowhere *silently* is what `Shell.tsx` records
 * 3A shipping six of. Building it now is the other half of that rule rather than a reversal.
 *
 * **It asks first.** Every other control on this page reads; this one ends a run somebody may
 * have been waiting hours for, and `wiener.md` §11 requires approval by a named human for
 * exactly that reason. The confirm step is where the *why* is collected, because the audit row
 * has nowhere else to get it — §11's line is *who · when · why · prior phase · resulting run
 * id*, and `why` is the only one a person has to supply.
 */
/** The mutation, **returned whole so its error is its caller's** — `reported.test.ts` holds
 *  that rule for every `useMutation` in the codebase, and it caught this file when the
 *  mutation lived inside the component. A refusal here is a sentence somebody has to see:
 *  *this run is already succeeded*, not a button that quietly does nothing. */
export function useCancel(runId: string, onDone: () => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (why: string) =>
      post<{ outcome: string; message: string }>(`/api/runs/${runId}/cancel`, { why }),
    onSuccess: () => {
      onDone();
      // The phase moves through the record, so the page learns it the same way it learns
      // everything else — by reading the run again rather than by being told here.
      client.invalidateQueries({ queryKey: ["run", runId] });
      client.invalidateQueries({ queryKey: ["overview", runId] });
    },
  });
}

export function Cancel({ runId }: { runId: string }) {
  const [asking, setAsking] = useState(false);
  const [why, setWhy] = useState("");
  const send = useCancel(runId, () => setAsking(false));

  if (!asking) {
    return (
      <button
        type="button"
        data-testid="cancel-run"
        onClick={() => setAsking(true)}
        className="font-data text-label uppercase tracking-[.08em] px-[15px] py-2
                   bg-transparent border border-line text-ink-3 cursor-pointer hover:text-ink"
        style={{ transition: `color var(--t)` }}
      >
        cancel
      </button>
    );
  }

  return (
    <span data-testid="cancel-confirm" className="flex items-center gap-2">
      {/* **Optional, and it says so.** A required reason turns an urgent stop into a form, and
          somebody watching a run burn money will type a character to get past it — which is a
          worse audit row than an empty one, because it looks like a reason. */}
      <input
        aria-label="why"
        value={why}
        placeholder="why (optional)"
        onChange={(event) => setWhy(event.target.value)}
        className="text-secondary bg-surface border border-line rounded-[var(--r)] px-2 py-1"
      />
      <button
        type="button"
        data-testid="cancel-confirm-yes"
        disabled={send.isPending}
        onClick={() => send.mutate(why)}
        className="font-data text-label uppercase tracking-[.08em] px-[15px] py-2
                   bg-transparent border cursor-pointer"
        style={{ color: "var(--fault)", borderColor: "var(--fault)" }}
      >
        {send.isPending ? "stopping…" : "stop this run"}
      </button>
      <button
        type="button"
        onClick={() => { setAsking(false); setWhy(""); }}
        className="bg-transparent border-0 text-label text-ink-3 cursor-pointer hover:text-ink"
      >
        keep it running
      </button>
      {/* A refusal is a sentence a person can act on — *this run is already succeeded*, never
          *cannot cancel*. Shown here rather than swallowed, because the button will otherwise
          look broken. */}
      {send.isError && (
        <span data-testid="cancel-error" className="text-label" style={{ color: "var(--fault)" }}>
          {String((send.error as Error)?.message ?? "the run could not be cancelled")}
        </span>
      )}
    </span>
  );
}
