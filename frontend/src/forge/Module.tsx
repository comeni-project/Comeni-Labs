import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";

type ModulePage = components["schemas"]["ModulePage"];
type Port = components["schemas"]["Port"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

function Ports({ title, ports }: { title: string; ports: Port[] }) {
  if (ports.length === 0) return null;
  return (
    <div className="mt-5">
      <div className={label}>{title}</div>
      {ports.map((p) => (
        <div key={p.name} className="flex items-baseline gap-4 py-1 text-body">
          <span className="font-data text-ink-2">{p.name}</span>
          <span className="font-data text-ink">{p.type_id}</span>
        </div>
      ))}
    </div>
  );
}

/** One row of the right column: a count, then the ids behind it.
 *
 * The count comes first because it is the answer — *is anything aiming at this?* — and the
 * list is the evidence for it.
 */
function Points({ title, ids }: { title: string; ids: string[] }) {
  return (
    <div className="mt-5">
      <div className={label}>
        {ids.length} {title}
      </div>
      {ids.map((id) => (
        <Link
          key={id}
          to={`/forge/contracts/${id}`}
          className="block font-data text-secondary text-pea no-underline py-1"
        >
          {id}
        </Link>
      ))}
    </div>
  );
}

/** A contract, the module it describes, and everything that points at it.
 *
 * **Dense is correct here** — design §7: it is browsed, not burned through, so it has
 * different rules from the queue.
 *
 * **Read only.** Nothing on this page writes; contracts change through the queue or through
 * drift resolution, both of which record *why*.
 */
export function Module({ id }: { id: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["contract", id],
    queryFn: () => get<ModulePage>(`/contracts/${id}`),
    enabled: id !== "",
  });

  if (isLoading) return <Loading what={id} />;
  if (error) return <Refusal message={String((error as Error).message)} />;
  if (!data) return <Failed error={`no contract called ${id}`} />;

  return (
    <div className="overflow-auto p-6">
      <Link to="/forge/contracts" className="text-secondary text-ink-3 no-underline">
        ← contracts
      </Link>

      <h1 className="font-data text-title mt-4">{data.id}</h1>
      <p className="text-secondary text-ink-3 mt-1 font-data">{data.roles.join(", ")}</p>

      <div className="grid grid-cols-[1fr_320px] gap-10 mt-6 max-w-[1100px]">
        <div>
          {data.container && (
            <div>
              <div className={label}>Container</div>
              <div className="font-data text-secondary text-ink-2 mt-1 break-all">
                {data.container}
              </div>
            </div>
          )}

          <Ports title="Consumes" ports={data.consumes} />
          <Ports title="Produces" ports={data.produces} />

          <div className="mt-6 border-l-2 border-line-2 pl-4">
            {data.emits_total === null ? (
              // **Not "0 of 0".** A module nobody could open has an unknown channel count,
              // and reporting zero is the same falsehood as folding `skipped` into
              // `matching`.
              <p className="text-body text-ink-2">No module source to read.</p>
            ) : (
              <>
                <p className="text-body text-ink">
                  <b className="font-data">
                    {data.emits_declared} of {data.emits_total}
                  </b>{" "}
                  emit channels declared
                </p>
                <p className="text-secondary text-ink-3 mt-1">
                  A contract may model a subset of what a module emits — nothing here
                  distinguishes a channel considered and omitted from one that was missed.
                </p>
              </>
            )}
            {data.source_path && (
              <p className="text-secondary text-ink-3 mt-2 font-data">{data.source_path}</p>
            )}
          </div>
        </div>

        <aside className="border-l border-line pl-6">
          <div className={label}>Points at this module</div>
          <Points title="rules aim at its roles" ids={data.rules_aiming} />
          <Points title="feed its inputs" ids={data.inputs_from} />
          <Points title="consume its outputs" ids={data.outputs_feed} />
          <Points title="compete with it" ids={data.competes_with} />
          <p className="mt-5 text-secondary text-ink-3">
            {/* Stated rather than omitted: a reader comparing this to the design must not
                have to guess whether the row was forgotten. */}
            pipeline pins — not tracked yet
          </p>
        </aside>
      </div>
    </div>
  );
}
