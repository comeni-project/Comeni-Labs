import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get, Refused } from "../api/client";
import type { components } from "../api/schema";
import { useAccept } from "../api/useAccept";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";

type DriftReport = components["schemas"]["DriftReport"];
type FieldCheck = components["schemas"]["FieldCheck"];
type Unchecked = components["schemas"]["Unchecked"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** The verdict block — the highest-value element on the maintenance half.
 *
 * The sentence comes from the API rather than being composed here: it is derived from a total
 * classification of the contract's fields, and a second sentence written in the browser would
 * be a second answer to *does this change what gets built?*
 */
function Verdict({ report }: { report: DriftReport }) {
  return (
    <div
      data-verdict={report.verdict}
      className="mt-6 border-l-2 pl-4 py-1 border-line-2
                 data-[verdict=breaks]:border-fault data-[verdict=reroutes]:border-fault"
    >
      <div
        data-verdict={report.verdict}
        className={`${label} data-[verdict=breaks]:text-fault
                    data-[verdict=reroutes]:text-fault`}
      >
        {report.verdict}
      </div>
      <p className="text-body text-ink mt-1 max-w-[70ch]">{report.says}</p>
    </div>
  );
}

/** One checked field: what each side says, and where the source says it. */
function Check({ check }: { check: FieldCheck }) {
  return (
    <div className="grid grid-cols-[150px_1fr] gap-6 items-baseline py-3 border-b border-line">
      <span className="font-data text-body">{check.field}</span>
      <div>
        <div className="text-secondary text-ink-3">
          registry <span className="font-data text-ink break-all">{check.registry_says}</span>
        </div>
        <div className="text-secondary text-ink-3 mt-1">
          source <span className="font-data text-ink break-all">{check.source_says}</span>
        </div>
        {check.locator && (
          // Only where the fact was read off a line. `nf_include` is synthesised from the
          // convention, so it has no locator and must not be presented as a quotation.
          <div className="mt-2 text-secondary text-ink-3">
            <div className="font-data">{check.locator}</div>
            {check.excerpt && (
              <pre className="font-data text-ink-2 mt-1 overflow-x-auto">{check.excerpt}</pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Take the source's value. `why` is required — a value changed with no reason recorded is
 * the one thing this artifact exists not to contain. */
function Take({ id, check, by }: { id: string; check: FieldCheck; by: string }) {
  const [who, setWho] = useState(by);
  const [why, setWhy] = useState("");
  const accept = useAccept(id);

  const field = "border border-line rounded px-2 py-1 bg-transparent text-body text-ink";
  return (
    <div className="mt-5 border-t border-line-2 pt-4">
      <div className={label}>Take the source's value for {check.field}</div>
      <div className="flex flex-wrap items-center gap-3 mt-2">
        <input
          className={field}
          value={who}
          aria-label="who"
          onChange={(e) => setWho(e.target.value)}
        />
        <input
          className={`${field} flex-1 min-w-[260px]`}
          value={why}
          aria-label="why"
          placeholder="why this is the right value now"
          onChange={(e) => setWhy(e.target.value)}
        />
        <button
          disabled={why.trim() === "" || accept.isPending}
          onClick={() => accept.mutate({ field: check.field, by: who, why })}
          className="px-3 py-1 rounded border border-pea text-pea bg-transparent
                     cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Take the source's value
        </button>
      </div>
      {accept.error && (
        <div className="mt-3">
          <Refusal
            message={
              accept.error instanceof Refused
                ? accept.error.message
                : String((accept.error as Error).message)
            }
          />
        </div>
      )}
      {accept.data && (
        <p className="text-secondary text-ink-3 mt-3 font-data">
          {accept.data.branch} · {accept.data.commit.slice(0, 8)} · {accept.data.path}
        </p>
      )}
    </div>
  );
}

/** The fields nothing checks — on the screen rather than left out of it.
 *
 * Three of the five fields the router reads are here, and a report that listed only what it
 * checked would read as a clean bill of health over an unchecked half. Spec §3.2.
 */
function Nothing({ fields }: { fields: Unchecked[] }) {
  const routes = fields.filter((f) => f.impact === "routes").map((f) => f.field);
  return (
    <div className="mt-8">
      <div className={label}>{fields.length} fields nothing checks</div>
      <p className="font-data text-body text-ink-2 mt-2">
        {fields.map((f) => f.field).join(", ")}
      </p>
      <p className="text-secondary text-ink-3 mt-2 max-w-[70ch]">
        {routes.length} of them — <span className="font-data">{routes.join(", ")}</span> — are
        read by the router. A port's <span className="font-data">type_id</span> is the most
        consequential value in a contract and no source can state it, which is why it is a
        question a human answers rather than a fact anything can verify.
      </p>
    </div>
  );
}

/** What moved between a contract and its source — a STATE of a contract, not a destination. */
export function Drift({ id }: { id: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["drift", id],
    queryFn: () => get<DriftReport>(`/contracts/${id}/drift`),
    enabled: id !== "",
  });

  if (isLoading) return <Loading what={`what moved under ${id}`} />;
  if (error) return <Refusal message={String((error as Error).message)} />;
  if (!data) return <Failed error={`no contract called ${id}`} />;

  const moved = data.checks.filter((c) => !c.agrees);
  const agreeing = data.checks.filter((c) => c.agrees);

  return (
    <div className="overflow-auto p-6">
      <Link to={`/forge/contracts/${id}`} className="text-secondary text-ink-3 no-underline">
        ← {id}
      </Link>

      <h1 className="font-data text-title mt-4">What moved</h1>
      {!data.verifiable && (
        <p className="text-secondary text-ink-3 mt-1">
          No registered source can re-read this contract, so only its module was checked.
        </p>
      )}

      <Verdict report={data} />

      <div className="mt-8 max-w-[900px]">
        <div className={label}>Fields checked</div>
        {moved.map((c) => (
          <Check key={c.field} check={c} />
        ))}
        {moved.length === 0 && (
          <p className="text-body text-ink-2 mt-2">
            The registry says what its source says, on every field anything can check.
          </p>
        )}

        {agreeing.length > 0 && (
          <details className="mt-3">
            <summary className="text-secondary text-ink-3 cursor-pointer">
              {agreeing.length} further {agreeing.length === 1 ? "field" : "fields"} checked,
              all matching
            </summary>
            {agreeing.map((c) => (
              <Check key={c.field} check={c} />
            ))}
          </details>
        )}

        {moved.map((c) => (
          <Take key={c.field} id={id} check={c} by="" />
        ))}
      </div>

      {data.conformance.length > 0 && (
        <div className="mt-8 max-w-[900px]">
          <div className={label}>What the module no longer supports</div>
          {data.conformance.map((d) => (
            <div key={`${d.code}-${d.where}`} className="mt-3">
              <Refusal message={`${d.code}: ${d.summary}`} />
              <p className="text-secondary text-ink-3 mt-1 pl-4">{d.fix}</p>
            </div>
          ))}
          <p className="text-secondary text-ink-3 mt-3 max-w-[70ch]">
            {/* No accept button here, and the reason is the point: a structural
                disagreement has no single source value to take. */}
            There is nothing to take here. Which emit label a renamed channel now means is a
            judgement, and a judgement goes through the queue as a re-draft.
          </p>
        </div>
      )}

      <Nothing fields={data.unchecked} />
    </div>
  );
}
