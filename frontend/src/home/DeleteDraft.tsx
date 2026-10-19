import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { remove } from "../api/client";

/** Delete a pipeline — **permanent**, so it asks first and says what goes (Part H).
 *
 * The confirmation names what is lost with it and points at *Data retention*, where the
 * installation's own limits are set, so nobody learns of a limit only by finding something gone.
 */
export function useDeleteDraft(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => remove(`/pipeline/drafts/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

export function DeleteDraft({ id, name }: { id: string; name: string }) {
  const [asking, setAsking] = useState(false);
  const send = useDeleteDraft(id);

  if (!asking) {
    return (
      <button type="button" data-testid="delete-draft" aria-label={`Delete ${name || id}`}
              onClick={() => setAsking(true)}
              className="bg-transparent border-0 p-0 text-secondary text-ink-3 cursor-pointer
                         hover:text-ink focus-visible:shadow-[var(--ring)]">
        Delete
      </button>
    );
  }
  return (
    <span data-testid="delete-draft-confirm" className="flex flex-wrap items-center justify-end gap-2
                                                       text-secondary text-ink-2">
      <span>
        Permanent: the pipeline, its conversation, its decisions and its gate results go with
        it. Runs of it stay. Limits are in{" "}
        <Link to={{ search: "?settings=retention" }} className="text-now-ink">
          Data retention settings
        </Link>.
      </span>
      <button type="button" data-testid="delete-draft-yes" disabled={send.isPending}
              onClick={() => send.mutate()}
              className="bg-transparent border px-2 py-[2px] cursor-pointer"
              style={{ color: "var(--needs-you)", borderColor: "var(--needs-you)" }}>
        {send.isPending ? "deleting…" : "delete it"}
      </button>
      <button type="button" data-testid="delete-draft-no" onClick={() => setAsking(false)}
              className="bg-transparent border-0 p-0 text-ink-3 cursor-pointer hover:text-ink">
        keep it
      </button>
      {send.error && <span role="alert" className="basis-full text-right"
                           style={{ color: "var(--needs-you)" }}>{send.error.message}</span>}
    </span>
  );
}
