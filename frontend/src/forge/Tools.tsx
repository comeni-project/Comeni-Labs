import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useTitle } from "../app/useTitle";
import { get, Refused } from "../api/client";
import type { components } from "../api/schema";
import { useDraft } from "../api/useDraft";
import { useUrlState } from "../app/useUrlState";
import { Refusal } from "../ui/Refusal";
import { Empty, Failed, Loading } from "../ui/States";
import { StatusBoard } from "./Board";
import { STANDING, type Standing } from "./standing";

type Board = components["schemas"]["Board"];
type BoardRow = components["schemas"]["BoardRow"];


/** A tool's status when it has one, and its stage when it does not.
 *
 * **Not two columns.** An undrafted tool has no agreement status and a landed one's stage adds
 * nothing its status does not already say, so the two axes collapse into one mark for every row.
 */
function standingOf(row: BoardRow): Standing {
  return (row.status ?? row.state) as Standing;
}

/** Start a draft.
 *
 * **The version is asked for and never prefilled.** Two of the thirteen vendored tools have a
 * container with no version in it at all, and one shipped contract disagrees with the tag it does
 * have — so a prefilled field would look authoritative and be wrong a third of the time. What the
 * source states is shown beside it, as evidence, which is what every other answer here is given.
 */
function Start({ row, onClose }: { row: BoardRow; onClose: () => void }) {
  const [name, setName] = useState(row.tool.split("/").pop() ?? "");
  const [version, setVersion] = useState("");
  const draft = useDraft();
  const go = useNavigate();
  const field = "border border-line-2 rounded-r px-2 py-1 bg-surface text-body text-ink";

  return (
    <div className="col-span-full flex flex-wrap items-center gap-3 pt-3">
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
          draft.mutate({ ref: row.ref, name, version }, { onSuccess: () => go("/forge/queue") })
        }
        className="px-3 py-1 rounded-r border border-pea text-pea bg-transparent cursor-pointer
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Draft it
      </button>
      <button
        onClick={onClose}
        className="text-secondary text-ink-3 bg-transparent border-0 cursor-pointer"
      >
        cancel
      </button>
      {draft.error && (
        <div className="w-full">
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

/** One tool. **One row shape for every stage**, which is the whole point of the merge.
 *
 * A second row component would put spec §1.3's mistake back into the markup: two screens for one
 * object's life is what made a person have to learn that a tool is one thing here and another
 * thing there.
 */
function Row({ row }: { row: BoardRow }) {
  const [starting, setStarting] = useState(false);
  const standing = standingOf(row);
  const flow = [...row.consumes, "→", ...row.produces];

  return (
    <div
      data-testid="tool-row"
      data-state={row.state}
      className="grid grid-cols-[16px_260px_1fr_auto] gap-4 items-baseline
                 px-6 py-2 border-b border-line hover:bg-surface-2"
    >
      <span
        data-testid="standing"
        data-standing={standing}
        title={STANDING[standing]?.title ?? standing}
        aria-label={STANDING[standing]?.title ?? standing}
        className={`w-2.5 h-2.5 self-center rounded-full ${STANDING[standing]?.mark ?? ""}`}
      />

      {row.contract_id ? (
        <Link
          to={`/forge/contracts/${row.contract_id}`}
          className="font-data text-body text-ink no-underline hover:text-pea"
        >
          {row.tool}
        </Link>
      ) : (
        <span className="font-data text-body text-ink-2">{row.tool}</span>
      )}

      <span className="font-data text-secondary text-ink-3 truncate">
        {row.open_questions > 0 ? (
          <Link to="/forge/queue" className="text-measured no-underline">
            {row.open_questions} open
          </Link>
        ) : row.consumes.length || row.produces.length ? (
          flow.join(" ")
        ) : (
          "—"
        )}
      </span>

      {row.state === "undrafted" && !starting && (
        <button
          onClick={() => setStarting(true)}
          className="text-secondary text-pea bg-transparent border-0 cursor-pointer p-0"
        >
          draft →
        </button>
      )}
      {starting && <span />}
      {starting && <Start row={row} onClose={() => setStarting(false)} />}
    </div>
  );
}

/** Every tool, at whatever stage of its life it has reached.
 *
 * **This replaces `Sources` and `Contracts`**, which asked the same question of the same objects
 * at two stages — spec §1.3. Both carried a `Facets` rail with the same docstring, written twice
 * independently, which is the clearest possible sign nobody had noticed.
 */
export function Tools() {
  useTitle("Tools");
  const [state] = useUrlState("state", "");
  const [against] = useUrlState("against", "");
  const [q, setQ] = useState("");

  const search = new URLSearchParams();
  if (state) search.set("state", state);
  if (against) search.set("against", against);
  const query = search.toString();

  const { data, isLoading, error } = useQuery({
    queryKey: ["tools", query],
    queryFn: () => get<Board>(`/tools${query ? `?${query}` : ""}`),
  });

  const rows = (data?.rows ?? []).filter((row) => row.tool.includes(q.trim()));

  return (
    <div className="overflow-auto">
      {data && <StatusBoard board={data} />}

      <div className="flex flex-wrap items-center gap-2 px-6 py-3 border-b border-line">
        <input
          aria-label="filter by name"
          placeholder="filter"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="border border-line-2 rounded-r px-2 py-1 bg-surface font-data
                     text-secondary text-ink w-[180px]"
        />
        {(state || against) && (
          <span className="text-secondary text-ink-3">
            showing <b className="text-ink">{state || against}</b> — click the figure above to
            clear
          </span>
        )}
      </div>

      {isLoading && <Loading what="every tool" />}
      {error && <Failed error={error} />}
      {!isLoading && !error && rows.length === 0 && (
        // **An empty state explains the screen, not the filter.** The one this replaces said
        // *"Nothing here. Clear the facet to see every contract."* — which assumes you already
        // know what a contract is, and the operator's verdict on 2026-08-19 was that nowhere in
        // the product said.
        <Empty
          title={
            q || state || against
              ? "No tool matches that."
              : "No source can see a tool yet."
          }
          next={
            q || state || against
              ? "Clear the filter above. This page lists every tool a source can read, at whatever stage it has reached — nobody has drafted it, somebody is drafting it, or it has landed in the registry."
              : "A source reads tools out of vendored modules. Until one does, there is nothing to draft."
          }
        />
      )}
      {rows.map((row) => (
        <Row key={row.ref} row={row} />
      ))}
    </div>
  );
}
