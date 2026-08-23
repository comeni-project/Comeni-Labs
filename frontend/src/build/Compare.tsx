import { useState } from "react";

import type { components } from "../api/schema";

type AlignedStep = components["schemas"]["AlignedStep"];
type Alignment = AlignedStep["state"];

/** What each alignment state is called where a person reads it, and what it means.
 *
 * **Four words, declared once.** The tier vocabulary was hardcoded in a React file with a second
 * copy in `dashboard.html` and nothing holding them together, and the operator was right to ask
 * whether the bar was invented. These four are not a *vocabulary the server owns* — the server
 * declares the states, this declares their English — but they live in one place for the same
 * reason.
 */
const WORDS: Record<Alignment, { label: string; what: string }> = {
  same: { label: "Same", what: "you and Mendel chose the same contract" },
  differs: { label: "Differs", what: "both have a step here and chose differently" },
  "yours-only": { label: "Yours only", what: "Mendel did not reach for this step" },
  "mendel-only": { label: "Mendel only", what: "Mendel would add this and you have not" },
};

const ORDER: Alignment[] = ["differs", "mendel-only", "yours-only", "same"];

function tool(contractId: string | null | undefined): string {
  if (!contractId) return "—";
  return contractId.split("@")[0].split("/").slice(1).join("/");
}

/** Your pipeline beside the one the resolver would build.
 *
 * **This is what Galaxy does not do.** Legality is the floor — `validate` covers that. This is
 * the screen's argument: the deterministic engine would have built *that*, you drew *this*, and
 * here is every place they part company, with the resolver's own reason for its half.
 *
 * **Adopting rewrites your graph locally; keeping yours is an override that needs a reason.**
 * `ProducerDecision.human_override` has existed since Plan 1.10 for exactly this, and one with
 * no reason is the defect A77 was — a person's answer replaced by *"selected the first of 1
 * candidates without judgement"*.
 */
export function Compare({
  alignment,
  onAdopt,
  onKeep,
}: {
  alignment: AlignedStep[] | null;
  onAdopt: (row: AlignedStep) => void;
  onKeep: (row: AlignedStep, reason: string) => void;
}) {
  const [keeping, setKeeping] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  if (alignment === null) {
    // **Not an empty diff.** A table with no rows reads as "you and Mendel agree", which is a
    // claim, and nothing has been compared yet.
    return (
      <p data-testid="compare-idle" className="p-4 text-secondary text-ink-3">
        Nothing compared yet. <b className="text-ink">Compare</b> resolves the goal and shows
        where your pipeline and Mendel's part company.
      </p>
    );
  }

  const rows = [...alignment].sort(
    (a, b) => ORDER.indexOf(a.state) - ORDER.indexOf(b.state),
  );
  const parting = rows.filter((r) => r.state !== "same").length;

  return (
    <div data-testid="compare" className="flex flex-col gap-2 p-3">
      <p className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
        {parting === 0
          ? "Identical to what Mendel resolves"
          : `${parting} of ${rows.length} steps differ`}
      </p>

      {rows.map((row) => {
        const key = `${row.state}:${row.yours_node ?? ""}:${row.mendel_node ?? ""}`;
        const words = WORDS[row.state];
        return (
          <div
            key={key}
            data-testid="compare-row"
            data-state={row.state}
            className="rounded-r border border-line bg-surface p-2"
          >
            <div className="flex items-baseline gap-2">
              <span className="text-label uppercase tracking-[.1em] font-semibold text-ink-3">
                {words.label}
              </span>
              <span className="font-data text-body text-ink">
                {row.state === "mendel-only" ? tool(row.mendel_contract) : tool(row.yours_contract)}
              </span>
              {row.state === "differs" && (
                <span className="font-data text-body text-ink-3">
                  → {tool(row.mendel_contract)}
                </span>
              )}
            </div>

            {row.why && (
              <p data-testid="compare-why" className="mt-1 text-secondary text-ink-3">
                {row.why}
              </p>
            )}

            {row.state !== "same" && (
              <div className="mt-2 flex gap-2">
                <button
                  data-testid="adopt"
                  onClick={() => onAdopt(row)}
                  className="px-2 py-1 rounded-r border border-line bg-surface text-body
                             hover:bg-[var(--hover)]"
                >
                  {row.state === "yours-only" ? "Remove" : "Adopt Mendel's"}
                </button>
                <button
                  data-testid="keep"
                  onClick={() => {
                    setKeeping(keeping === key ? null : key);
                    setReason("");
                  }}
                  className="px-2 py-1 rounded-r border border-line bg-surface text-body
                             hover:bg-[var(--hover)]"
                >
                  Keep mine
                </button>
              </div>
            )}

            {keeping === key && (
              <div className="mt-2 flex gap-2">
                <input
                  data-testid="keep-reason"
                  autoFocus
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why keep yours?"
                  className="flex-1 rounded-r border border-line bg-bg px-2 py-1 text-body"
                />
                <button
                  data-testid="keep-confirm"
                  // **An override with no reason is the defect A77 was.** The person answering
                  // is the only one who knows why, and until Plan 1.14 they had nowhere to say
                  // it — so `upgrade` replaced what they meant with the resolver's boilerplate.
                  disabled={reason.trim() === ""}
                  onClick={() => {
                    onKeep(row, reason.trim());
                    setKeeping(null);
                    setReason("");
                  }}
                  className="px-2 py-1 rounded-r border-0 bg-pea text-[var(--on-pea)] text-body
                             font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Keep
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
