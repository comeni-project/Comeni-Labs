import { useQuery } from "@tanstack/react-query";

import { get } from "../wiener/api/client";
import type { components } from "../wiener/api/schema";

type MeasuredOut = components["schemas"]["MeasuredOut"];
type Fact = components["schemas"]["MeasuredView"];

const STATUS: Record<Fact["status"], string> = {
  confirmed: "confirmed on all the data",
  disagrees: "disagrees with the estimate",
  measured: "measured in the run",
  undetermined: "could not be measured",
};

function shown(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

/** **What the run measured** (issues 465, 217): each fact a measuring step reported, beside the
 * estimate the pipeline was built on, and each value a setting decided at run time took. A
 * disagreement names the decisions that rested on the estimate: the run's value is what the data
 * says, and those decisions are flagged, never silently kept. Renders nothing when the run
 * measured nothing, as the other panels do for an empty record. */
export function Measured({ runId, live }: { runId: string; live: boolean }) {
  const found = useQuery({
    queryKey: ["measured", runId],
    queryFn: () => get<MeasuredOut>(`/api/runs/${runId}/measured`),
    refetchInterval: live ? 10_000 : false,
  });
  const facts = found.data?.facts ?? [];
  const decided = found.data?.decided ?? [];
  if (!facts.length && !decided.length) return null;
  const disagreeing = facts.filter((f) => f.status === "disagrees");

  return (
    <section data-testid="measured" className="flex flex-col gap-2">
      <h2 className="text-label text-ink-3 m-0">Measured in this run</h2>
      {disagreeing.length > 0 && (
        <p data-testid="measured-flag" className="m-0 text-secondary text-needs-you-ink">
          {disagreeing.length} {disagreeing.length === 1 ? "fact disagrees" : "facts disagree"} with
          what the pipeline was built on. Rebuild with the measured values before trusting these
          results.
        </p>
      )}
      <ul className="m-0 p-0 list-none flex flex-col gap-1">
        {facts.map((fact) => (
          <li key={`${fact.measurement}:${fact.sample}`} data-testid="measured-fact"
              data-status={fact.status} className="font-data text-secondary text-ink-2">
            <span className="text-ink">{fact.measurement}</span> is {shown(fact.value)} for{" "}
            {fact.sample} — {STATUS[fact.status]}
            {fact.status === "disagrees" && (
              <span data-testid="measured-estimate">
                {" "}(built on {shown(fact.estimate)}; used by {fact.used_by?.join(", ")})
              </span>
            )}
            {fact.status === "undetermined" && fact.reason && <span>: {fact.reason}</span>}
          </li>
        ))}
        {decided.map((value) => (
          <li key={`${value.step}.${value.setting}:${value.sample}`} data-testid="measured-decided"
              className="font-data text-secondary text-ink-2">
            {value.setting === "tool"
              ? <>{value.sample} went through {tool(value.value)} for {value.step}, chosen in the run</>
              : <>{value.step}.{value.setting} was {value.value} for {value.sample}, decided at run time</>}
            {value.facts && value.facts.length > 0 && (
              <span>
                {" "}from {value.facts.map((f) => `${f.fact} ${f.value} (${FROM[f.source]})`).join(", ")}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A tool as the run writes it, `nf-core.star.align:2.7.11b`, back to its id (issue 466). */
function tool(token: string): string {
  const at = token.lastIndexOf(":");
  return at < 0 ? token : `${token.slice(0, at).replaceAll(".", "/")}@${token.slice(at + 1)}`;
}

/** Where a decided value's fact came from (issue 466). */
const FROM: Record<"cell" | "measured" | "missing", string> = {
  cell: "from the samplesheet",
  measured: "measured in the run",
  missing: "not known",
};
