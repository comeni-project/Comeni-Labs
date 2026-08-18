import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useUrlState } from "../app/useUrlState";
import { Empty, Failed, Loading } from "../ui/States";

type Listing = components["schemas"]["Listing"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** The three statuses, with counts **over the whole registry**.
 *
 * A facet that counted only what is shown would read 12 in the one you are standing in and 0
 * in every other, which is the opposite of what a facet is for.
 *
 * `unverifiable` sits between drifted and matching rather than beside matching, because a
 * contract nothing could re-read is neither drifted nor agreeing — the distinction slice 1
 * shipped wrong once.
 */
function Facets({ counts }: { counts: Record<string, number> }) {
  const [against, setAgainst] = useUrlState("against", "");
  const order = ["drifted", "unverifiable", "matching"];

  return (
    <div className="border-r border-line p-6 flex flex-col">
      <div className={`${label} mb-3`}>Against source</div>
      {order.map((status) => (
        <button
          key={status}
          data-active={against === status || undefined}
          // Clicking the facet you are in clears it, so there is always a way back to
          // everything without reaching for the URL.
          onClick={() => setAgainst(against === status ? "" : status)}
          className="flex items-baseline gap-4 py-2 text-body text-left bg-transparent
                     border-0 cursor-pointer text-ink-2 data-[active]:text-ink
                     data-[active]:font-semibold"
        >
          <span>{status}</span>
          <b className="ml-auto font-data text-secondary font-semibold">
            {counts[status] ?? 0}
          </b>
        </button>
      ))}
      <div className="mt-auto text-label text-ink-3 leading-7">
        <div>Read only — contracts change</div>
        <div>through the queue or through drift.</div>
      </div>
    </div>
  );
}

/** What has landed, worst first. */
export function Contracts() {
  const [params] = useSearchParams();
  const search = params.toString();

  const { data, isLoading, error } = useQuery({
    queryKey: ["contracts", search],
    queryFn: () => get<Listing>(`/contracts${search ? `?${search}` : ""}`),
  });

  return (
    <div className="grid grid-cols-[216px_1fr] overflow-hidden">
      <Facets counts={data?.counts ?? {}} />
      <div className="overflow-auto">
        <div className="flex items-center gap-5 px-6 py-4 border-b border-line-2">
          <span className={label}>Contracts</span>
          <span className="ml-auto text-secondary text-ink-3">
            <span className="font-data">{data?.rows.length ?? 0}</span> shown ·{" "}
            <span className="font-data">{data?.total ?? 0}</span> in the registry
          </span>
        </div>

        {isLoading && <Loading what="the registry" />}
        {error && <Failed error={error} />}
        {data?.rows.length === 0 && !isLoading && (
          <Empty title="Nothing here." next="Clear the facet to see every contract." />
        )}

        {data?.rows.map((row) => (
          <div
            key={row.id}
            data-status={row.status}
            className="grid grid-cols-[110px_1fr_180px] gap-6 items-baseline px-6 py-4
                       border-b border-line"
          >
            <span
              data-status={row.status}
              className={`${label} data-[status=drifted]:text-fault
                          data-[status=unverifiable]:text-ink-2`}
            >
              {row.status}
            </span>
            <Link
              to={`/forge/contracts/${row.id}`}
              className="text-body font-data text-pea no-underline"
            >
              {row.id}
            </Link>
            <span className="text-secondary text-ink-3 font-data">{row.roles.join(", ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
