import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { get, Refused } from "../api/client";
import type { components } from "../api/schema";
import { useDraft } from "../api/useDraft";
import { useUrlState } from "../app/useUrlState";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";

type Catalogue = components["schemas"]["Catalogue"];
type ToolRow = components["schemas"]["ToolRow"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";
const field = "border border-line rounded px-2 py-1 bg-transparent text-body text-ink";

/** Three states, counted over everything discoverable rather than the filtered view.
 *
 * Same argument as the contracts list: a facet counting only what is shown reads 2 in the one
 * you are standing in and 0 in every other.
 */
function Facets({ counts }: { counts: Record<string, number> }) {
  const [state, setState] = useUrlState("state", "");
  return (
    <div className="border-r border-line p-6 flex flex-col">
      <div className={`${label} mb-3`}>State</div>
      {["undrafted", "drafted", "landed"].map((one) => (
        <button
          key={one}
          data-active={state === one || undefined}
          onClick={() => setState(state === one ? "" : one)}
          className="flex items-baseline gap-4 py-2 text-body text-left bg-transparent
                     border-0 cursor-pointer text-ink-2 data-[active]:text-ink
                     data-[active]:font-semibold"
        >
          <span>{one}</span>
          <b className="ml-auto font-data text-secondary font-semibold">{counts[one] ?? 0}</b>
        </button>
      ))}
      <div className="mt-auto text-label text-ink-3 leading-7">
        <div>Landing is still `forge land`.</div>
        <div>Drafting opens work; the queue closes it.</div>
      </div>
    </div>
  );
}

/** Start a draft.
 *
 * **The version is asked for and never prefilled.** Two of the thirteen vendored tools have a
 * container with no version in it at all, and one shipped contract disagrees with the tag it
 * does have — so a prefilled field would look authoritative and be wrong a third of the time.
 * What the source states is shown *beside* it, as evidence, which is what every other answer in
 * this interface is given.
 */
function Start({ row }: { row: ToolRow }) {
  const [name, setName] = useState(row.ref.split("/").pop() ?? "");
  const [version, setVersion] = useState("");
  const draft = useDraft();
  const go = useNavigate();

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-secondary text-ink-3">
          name
          <input
            className={field}
            aria-label="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-secondary text-ink-3">
          version
          <input
            className={field}
            aria-label="version"
            placeholder="the tool's version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
          />
        </label>
        <button
          disabled={name.trim() === "" || version.trim() === "" || draft.isPending}
          onClick={() =>
            draft.mutate(
              { ref: row.ref, name, version },
              { onSuccess: () => go("/forge/queue") },
            )
          }
          className="px-3 py-1 rounded border border-pea text-pea bg-transparent
                     cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Draft it
        </button>
      </div>
      {draft.error && (
        <div className="mt-3">
          <Refusal
            message={
              draft.error instanceof Refused
                ? draft.error.message
                : String((draft.error as Error).message)
            }
          />
        </div>
      )}
    </div>
  );
}

function Row({ row }: { row: ToolRow }) {
  return (
    <div
      data-testid="tool-row"
      data-state={row.state}
      className="grid grid-cols-[110px_1fr] gap-6 items-baseline px-6 py-4 border-b border-line"
    >
      <span
        data-state={row.state}
        className={`${label} data-[state=undrafted]:text-pea data-[state=drafted]:text-ink-2`}
      >
        {row.state}
      </span>
      <div>
        <div className="text-body font-data">{row.ref}</div>
        {row.contract_id && (
          <Link
            to={`/forge/contracts/${row.contract_id}`}
            className="text-secondary font-data text-pea no-underline"
          >
            {row.contract_id}
          </Link>
        )}
        {row.draft && (
          <Link
            to="/forge/queue?group=module"
            className="text-secondary font-data text-pea no-underline"
          >
            {row.draft} — answer it in the queue
          </Link>
        )}
        {row.state === "undrafted" && <Start row={row} />}
      </div>
    </div>
  );
}

/** What each source can read, and what has been done with it.
 *
 * **Drafting happens here rather than on a page of its own.** Design §3's rule: a page earns its
 * place by being a different *kind* of work, and starting a draft is the action this list exists
 * to offer rather than a different kind of work from browsing it.
 */
export function Sources() {
  const [state] = useUrlState("state", "");
  const query = state ? `?state=${state}` : "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["sources", state],
    queryFn: () => get<Catalogue>(`/sources${query}`),
  });

  return (
    <div className="grid grid-cols-[216px_1fr] overflow-hidden">
      <Facets counts={data?.counts ?? {}} />
      <div className="overflow-auto">
        <div className="flex items-center gap-5 px-6 py-4 border-b border-line-2">
          <span className={label}>Sources</span>
          <span className="ml-auto text-secondary text-ink-3 font-data">
            {(data?.sources ?? []).join(", ")}
          </span>
        </div>

        {isLoading && <Loading what="what the sources can read" />}
        {error && <Failed error={error} />}
        {data?.rows.map((row) => (
          <Row key={row.ref} row={row} />
        ))}
      </div>
    </div>
  );
}
