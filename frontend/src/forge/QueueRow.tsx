import type { components } from "../api/schema";

export type OpenQuestion = components["schemas"]["OpenQuestion"];

/** One row shape for every kind of work — `docs/design/forge-review.md` §3.
 *
 * Drift, proposals, questions and labels all render through this. A second row component
 * would be a second answer to "what does a piece of work look like", and the design's claim
 * that these are one surface would stop being true in the markup.
 */
export function QueueRow({ q }: { q: OpenQuestion }) {
  const n = q.asked_by.length;
  return (
    <div
      data-band={q.band}
      className="grid grid-cols-[72px_1fr_128px_54px] gap-6 items-baseline px-6 py-4
                 border-b border-line data-[band=cosmetic]:opacity-60"
    >
      <span
        className="text-label uppercase tracking-[.13em] font-semibold
                   data-[band=routing]:text-pea"
        data-band={q.band}
      >
        {q.suggested ? "Confirm" : "Ask"}
      </span>

      <div>
        <div className="text-body font-data">{q.subject}</div>
        <div className="text-secondary text-ink-2 mt-1">{q.what}</div>
      </div>

      <span className="text-secondary text-ink-3">
        {n} {n === 1 ? "module" : "modules"}
      </span>

      <a href="#" className="text-body text-pea no-underline">Answer</a>
    </div>
  );
}
