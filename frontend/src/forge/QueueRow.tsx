import { Link } from "react-router";

import type { components } from "../api/schema";

export type OpenQuestion = components["schemas"]["OpenQuestion"];

/** One row shape for every kind of work — `docs/design/forge-review.md` §3.
 *
 * Drift, proposals, questions and labels all render through this. A second row component
 * would be a second answer to "what does a piece of work look like", and the design's claim
 * that these are one surface would stop being true in the markup.
 */
export function QueueRow({
  q,
  selected = false,
  heading,
}: {
  q: OpenQuestion;
  selected?: boolean;
  heading?: string;
}) {
  const n = q.asked_by.length;
  return (
    <>
      {heading && (
        <div className="px-6 pt-5 pb-2 text-label uppercase tracking-[.13em]
                        font-semibold text-ink-3 font-data">
          {heading}
        </div>
      )}
    <div
      data-band={q.band}
      data-selected={selected || undefined}
      className="grid grid-cols-[72px_1fr_128px_54px] gap-6 items-baseline px-6 py-4
                 border-b border-line data-[band=cosmetic]:opacity-60
                 data-[selected]:shadow-[inset_2px_0_0_var(--pea)]
                 data-[selected]:bg-surface-2"
    >
      <span
        className="text-label uppercase tracking-[.13em] font-semibold
                   data-[band=routing]:text-pea data-[band=blocked]:text-fault"
        data-band={q.band}
      >
        {q.band === "blocked" ? "Blocked" : q.suggested ? "Confirm" : "Ask"}
      </span>

      <div>
        <div className="text-body font-data">{q.subject}</div>
        <div className="text-secondary text-ink-2 mt-1">{q.what}</div>
      </div>

      <span className="text-secondary text-ink-3">
        {n} {n === 1 ? "module" : "modules"}
      </span>

      <Link
        to={`/forge/queue/question/${encodeURIComponent(q.subject)}`}
        className="text-body text-pea no-underline"
      >
        Answer
      </Link>
    </div>
    </>
  );
}
