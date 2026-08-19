import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { get, Refused } from "../api/client";
import type { components } from "../api/schema";
import { useDraft } from "../api/useDraft";
import { useUrlState } from "../app/useUrlState";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";

type Board = components["schemas"]["Board"];
type BoardRow = components["schemas"]["BoardRow"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** Where a tool stands, as one mark.
 *
 * **One scale, five values, drawn rather than spelled.** The old contracts row spent a 110px
 * column on the word `unverifiable` and the old sources row spent another on `undrafted`, so two
 * screens used two vocabularies for one axis and neither could be scanned. A tool is somewhere on
 * a single line — nobody has drafted it, somebody is drafting it, it landed and agrees, it landed
 * and nothing can check it, it landed and no longer agrees — and the mark says which at a glance.
 *
 * Colours are the ones the tiers already carry: coral for something that was true and is not,
 * amber for a thing whose premise is unchecked, pea for settled. Nothing new was added.
 */
const STANDING: Record<string, { mark: string; title: string }> = {
  drifted: { mark: "bg-[var(--undecided)]", title: "landed, and no longer agrees with its source" },
  unverifiable: {
    mark: "bg-transparent border border-[var(--measured)]",
    title: "landed, and no source can re-read it",
  },
  matching: { mark: "bg-pea", title: "landed, and agrees with its source" },
  drafted: { mark: "bg-transparent border border-pea", title: "somebody is drafting it" },
  undrafted: { mark: "bg-transparent border border-line-2", title: "nobody has drafted it" },
};

function standingOf(row: BoardRow): string {
  return row.status ?? row.state;
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

/** A filter that says how many, and clears itself when clicked again. */
function Chip({
  name,
  n,
  active,
  onClick,
}: {
  name: string;
  n?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      data-active={active || undefined}
      onClick={onClick}
      className="flex items-baseline gap-2 px-3 py-1 rounded-r border border-line bg-transparent
                 cursor-pointer text-secondary text-ink-2 hover:border-line-2
                 data-[active]:border-pea data-[active]:text-ink data-[active]:font-semibold"
    >
      {name}
      {n !== undefined && <b className="font-data text-ink-3">{n}</b>}
    </button>
  );
}

/** Every tool, at whatever stage of its life it has reached.
 *
 * **This replaces `Sources` and `Contracts`**, which asked the same question of the same objects
 * at two stages — spec §1.3. Both carried a `Facets` rail with the same docstring, written twice
 * independently, which is the clearest possible sign nobody had noticed.
 */
export function Tools() {
  const [state, setState] = useUrlState("state", "");
  const [against, setAgainst] = useUrlState("against", "");
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
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 px-6 py-4 border-b border-line-2">
        <span className={label}>Tools</span>
        <span className="text-secondary text-ink-3">
          <b className="font-data text-ink">{data?.counts.landed ?? 0}</b> landed ·{" "}
          <b className="font-data text-ink">{data?.counts.drafted ?? 0}</b> drafted ·{" "}
          {/* **An absence, not a zero** — #77. Discovery reads `vendor/modules/`, so thirteen is
              the size of what somebody already vendored rather than the size of the known world.
              Rendering it as a catalogue total would be a claim; `—` is the truth. */}
          <b data-testid="known" className="font-data text-ink">
            {data?.known ?? "—"}
          </b>{" "}
          known
        </span>
        <span className="ml-auto text-secondary text-ink-3 font-data">
          {(data?.sources ?? []).join(", ")}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-6 py-3 border-b border-line">
        <input
          aria-label="filter by name"
          placeholder="filter"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="border border-line-2 rounded-r px-2 py-1 bg-surface font-data
                     text-secondary text-ink w-[180px]"
        />
        <span className="w-px h-5 bg-line mx-1" />
        {["undrafted", "drafted", "landed"].map((one) => (
          <Chip
            key={one}
            name={one}
            n={data?.counts[one]}
            active={state === one}
            onClick={() => setState(state === one ? "" : one)}
          />
        ))}
        <span className="w-px h-5 bg-line mx-1" />
        {["drifted", "unverifiable"].map((one) => (
          <Chip
            key={one}
            name={one}
            n={data?.status_counts[one]}
            active={against === one}
            onClick={() => setAgainst(against === one ? "" : one)}
          />
        ))}
      </div>

      {isLoading && <Loading what="every tool" />}
      {error && <Failed error={error} />}
      {rows.map((row) => (
        <Row key={row.ref} row={row} />
      ))}
    </div>
  );
}
