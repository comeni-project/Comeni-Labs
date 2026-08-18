import { useState } from "react";

import { usePropose } from "../api/usePropose";
import { Refusal } from "../ui/Refusal";

/** Invariant 7's escape hatch — *"nothing declared fits, and here is what would"*.
 *
 * **Inline, never behind a modal.** The design says never buried, and a modal is buried with
 * extra steps. A closed choice with no way to decline forces a wrong answer, which is the
 * defect `notes/specs/2026-08-17-vocabulary-proposals.md` was written about.
 *
 * **The hole stays open** after this succeeds. The question does not leave the queue; it
 * changes from *nobody has reached this* to *somebody looked and nothing fit*.
 */
export function NothingFits({ draft, subject }: { draft: string; subject: string }) {
  const [open, setOpen] = useState(false);
  const [id, setId] = useState("");
  const [description, setDescription] = useState("");
  const [why, setWhy] = useState("");
  const propose = usePropose();

  const ready = id.trim() && description.trim() && why.trim();

  const field = "block w-full mt-1 p-2 text-body border border-line-2 rounded-r bg-surface";
  const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mt-4 text-body text-ink-2 bg-transparent border-0 p-0 cursor-pointer underline"
      >
        Nothing here fits
      </button>
    );
  }

  return (
    <div className="mt-6 border-l-2 border-line-2 pl-4">
      <p className="text-body text-ink-2">
        Propose what <em>would</em> fit. A reviewer approves it before anything uses it, and this
        question stays open until they do.
      </p>

      <label className="block mt-4">
        <span className={label}>Proposed id</span>
        <input
          aria-label="proposed id"
          className={`${field} font-data`}
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
      </label>

      <label className="block mt-3">
        <span className={label}>Description</span>
        <input
          aria-label="description"
          className={field}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      <label className="block mt-3">
        <span className={label}>Why nothing fits</span>
        <textarea
          aria-label="why nothing fits"
          className={field}
          rows={2}
          value={why}
          onChange={(e) => setWhy(e.target.value)}
        />
      </label>

      {propose.error && (
        <div className="mt-3">
          <Refusal message={String((propose.error as Error).message)} />
        </div>
      )}

      {propose.isSuccess && (
        <p className="mt-3 text-body text-ink-2">
          Proposed. <b>This question stays open</b> until a reviewer approves it.
        </p>
      )}

      <div className="flex gap-3 mt-4">
        <button
          onClick={() => propose.mutate({ draft, subject, id, description, why })}
          disabled={!ready || propose.isPending}
          className="px-4 py-2 text-body font-semibold rounded-r border border-line-2
                     bg-surface cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {propose.isPending ? "Proposing…" : "Propose"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="px-4 py-2 text-body text-ink-2 bg-transparent border-0 cursor-pointer"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
