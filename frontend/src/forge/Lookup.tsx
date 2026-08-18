import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useUrlState } from "../app/useUrlState";
import { Refusal } from "../ui/Refusal";
import { Loading } from "../ui/States";

type TypeCard = components["schemas"]["TypeCard"];

/** The registry lookup — a panel, never a page.
 *
 * **It lives in the Shell**, so it survives navigation: you consult it mid-decision, and
 * navigating away from a question you are answering is the friction the design removes
 * (`forge-review.md` §3).
 *
 * **The counts are the decision aid.** *"2 consume this"* answers *is this the normal choice*,
 * which is the question a curator actually has and the one a description cannot answer. That
 * is the same argument `CLAUDE.md` makes for why there is no vector store: exact retrieval,
 * versioned and attributable, not similarity.
 */
export function Lookup() {
  const [id, setId] = useUrlState("lookup", "");

  const { data, isLoading, error } = useQuery({
    queryKey: ["type", id],
    queryFn: () => get<TypeCard>(`/registry/types/${encodeURIComponent(id)}`),
    enabled: id !== "",
  });

  if (id === "") return null;

  return (
    <aside
      className="fixed right-0 top-[54px] bottom-0 w-[320px] overflow-auto
                 bg-surface border-l border-line p-6"
    >
      <div className="flex items-baseline gap-3">
        <h2 className="font-data text-body text-ink">{id}</h2>
        <button
          onClick={() => setId("")}
          aria-label="close the lookup"
          className="ml-auto text-body text-ink-3 bg-transparent border-0 cursor-pointer"
        >
          ×
        </button>
      </div>

      {isLoading && <Loading what={id} />}
      {error && <Refusal message={String((error as Error).message)} />}

      {data && (
        <>
          <div className="mt-5">
            <div className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
              States
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {data.states.map((s) => (
                <span
                  key={s}
                  className="font-data text-secondary text-ink-2 border border-line-2
                             rounded-r px-2 py-1"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>

          <Users label="produces" ids={data.produced_by} verb="produces" />
          <Users label="consume" ids={data.consumed_by} verb="consume" />
        </>
      )}
    </aside>
  );
}

/** `N produces` / `N consume`, then the ids. The count first, because the count is the answer
 *  to the question being asked; the list is the evidence for it. */
function Users({ label, ids, verb }: { label: string; ids: string[]; verb: string }) {
  return (
    <div className="mt-5">
      <div className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
        {ids.length} {verb}
      </div>
      {ids.length === 0 ? (
        <p className="text-secondary text-ink-3 mt-2">
          Nothing in this registry {label === "produces" ? "produces" : "consumes"} it yet.
        </p>
      ) : (
        <ul className="list-none p-0 mt-2">
          {ids.map((c) => (
            <li key={c} className="font-data text-secondary text-ink-2 py-1">
              {c}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
