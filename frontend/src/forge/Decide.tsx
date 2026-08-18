import { useState } from "react";

import type { components } from "../api/schema";
import { useDecide } from "../api/useDecide";
import { Refusal } from "../ui/Refusal";

type Proposal = components["schemas"]["Proposal"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";
const field = "block w-full mt-1 p-2 text-body border border-line-2 rounded-r bg-surface";

/** Approve, rename or reject — design §3's *"a proposal is an item in the queue"*, decided
 *  on the question it belongs to rather than on a page of its own.
 *
 * **A decided proposal shows no buttons.** It is a record; re-deciding it is not a phase 3
 * verb, and offering a button for something the API has no route for is the dead-link defect
 * phase 0 spent a task removing.
 */
export function Decide({
  draft,
  subject,
  proposal,
}: {
  draft: string;
  subject: string;
  proposal: Proposal;
}) {
  const [id, setId] = useState(proposal.id);
  const [why, setWhy] = useState("");
  const decide = useDecide();

  const ready = why.trim().length > 0;
  const settled = proposal.decision !== "open";

  return (
    <div className="mt-4 border-l-2 border-line-2 pl-4">
      <p className="text-body text-ink">
        {settled ? "Was proposed" : "Nothing declared fits"} —{" "}
        <span className="font-data">{proposal.id}</span>, by{" "}
        <span className="font-data">{proposal.by}</span>
      </p>
      <p className="text-secondary text-ink-2 mt-1">{proposal.description}</p>
      <p className="text-secondary text-ink-3 mt-1">{proposal.why}</p>

      {settled && (
        <p className="text-body text-ink mt-3">
          <b>{proposal.decision}</b>
          {proposal.decided_id && (
            <>
              {" "}
              as <span className="font-data">{proposal.decided_id}</span>
            </>
          )}{" "}
          by <span className="font-data">{proposal.decided_by}</span> — {proposal.decided_why}
        </p>
      )}

      {!settled && (
        <>
          <label className="block mt-4">
            <span className={label}>Approve as</span>
            <input
              aria-label="approve as"
              className={`${field} font-data`}
              value={id}
              onChange={(e) => setId(e.target.value)}
            />
          </label>

          <label className="block mt-3">
            <span className={label}>Reason</span>
            <textarea
              aria-label="reason"
              className={field}
              rows={2}
              value={why}
              onChange={(e) => setWhy(e.target.value)}
            />
          </label>

          {decide.error && (
            <div className="mt-3">
              <Refusal message={String((decide.error as Error).message)} />
            </div>
          )}

          <div className="flex gap-3 mt-4">
            <button
              onClick={() =>
                decide.mutate({
                  draft,
                  subject,
                  decision: "approved",
                  // `null` when the reviewer left the proposed id alone, so a rename is
                  // visible in the payload rather than inferred from it matching.
                  id: id === proposal.id ? null : id,
                  why,
                })
              }
              disabled={!ready || decide.isPending}
              className="px-4 py-2 text-body font-semibold rounded-r border border-line-2
                         bg-surface cursor-pointer disabled:opacity-40
                         disabled:cursor-not-allowed"
            >
              Approve
            </button>
            <button
              onClick={() =>
                decide.mutate({ draft, subject, decision: "rejected", id: null, why })
              }
              disabled={!ready || decide.isPending}
              className="px-4 py-2 text-body rounded-r border border-line-2 bg-surface
                         cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Reject
            </button>
          </div>
        </>
      )}
    </div>
  );
}
