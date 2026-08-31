import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get, post } from "../api/client";
import type { components } from "../api/schema";
import type { DraftGraph, Verdict } from "../api/types";
import { Failed, Loading } from "../ui/States";

type Candidates = components["schemas"]["Candidates"];
type Step = components["schemas"]["StepView"];

/** Swap a step for something else — **shown, then asked.**
 *
 * `n-bswap`: *four changes listed, nothing applied until you say so. A resolver that silently
 * rewrites four things is indistinguishable from one that guessed.*
 *
 * ═══ THE CONSEQUENCES ARE COMPUTED, NOT DESCRIBED ═════════════════════════════════════════
 *
 * Choosing a candidate runs `POST /pipeline/validate` against the graph **as it would be** and
 * diffs the verdict against the one that holds now. So *this would leave `star_align.index`
 * unmet* is a finding the resolver produced about a real graph, not a sentence predicting what
 * it might say.
 *
 * That is the same discipline as the picker's ordering and `compare`'s reasons: the engine
 * answers, the screen renders. `compare` does this at pipeline scale against the resolver's own
 * choice; this is one node, against a choice you are considering.
 *
 * ═══ NOTHING IS APPLIED UNTIL IT IS ═══════════════════════════════════════════════════════
 *
 * `replaceContract` is not called while you look. The preview is a query on a graph that exists
 * only as an argument.
 */
export function Swap({ step, graph, onApply, onClose }: {
  step: Step;
  graph: DraftGraph;
  onApply: (contractId: string) => void;
  onClose: () => void;
}) {
  const [chosen, setChosen] = useState<string | null>(null);

  // What else makes what this step makes. An alternative that produced something different
  // would not be a swap, it would be a different pipeline.
  const out = step.ports.find((p) => p.side === "out");

  const options = useQuery({
    queryKey: ["candidates", out?.type_id, (out?.states ?? []).join(","), "producing"],
    enabled: Boolean(out),
    queryFn: () =>
      get<Candidates>(
        `/pipeline/candidates?type_id=${encodeURIComponent(out!.type_id)}`
        + `&states=${encodeURIComponent((out!.states ?? []).join(","))}&side=producing`,
      ),
  });

  /** The graph as it WOULD be. Built here and sent; never written back. */
  const hypothetical: DraftGraph | null = chosen
    ? {
      ...graph,
      nodes: graph.nodes.map((n) =>
        (n.id === step.id ? { ...n, contract_id: chosen } : n)),
    }
    : null;

  const now = useQuery({
    queryKey: ["validate-now", JSON.stringify(graph)],
    queryFn: () => post<Verdict>("/pipeline/validate", graph),
  });

  const would = useQuery({
    queryKey: ["validate-would", chosen, JSON.stringify(graph)],
    enabled: hypothetical !== null,
    queryFn: () => post<Verdict>("/pipeline/validate", hypothetical!),
  });

  // A finding is identified by its code and where it landed. `node` and `port` are the
  // fields `Finding` actually carries — there is no `where`.
  const key = (f: { code: string; node?: string | null; port?: string | null }) =>
    `${f.code} ${f.node ?? ""}${f.port ? "." + f.port : ""}`.trim();
  const before = new Set((now.data?.findings ?? []).map(key));
  const after = (would.data?.findings ?? []).map(key);
  const added = after.filter((k) => !before.has(k));
  const fixed = [...before].filter((k) => !after.includes(k));

  const alternatives = (options.data?.candidates ?? [])
    .filter((row) => row.contract_id !== step.contract_id);

  return (
    <div data-testid="swap" className="p-3 flex flex-col gap-3">
      <div className="flex items-baseline gap-2">
        <span className="text-label uppercase tracking-[.13em] text-ink-3">Swap</span>
        <span className="font-data text-secondary text-ink">{step.process}</span>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto text-secondary text-ink-3 bg-transparent border-0 cursor-pointer p-0"
        >
          cancel
        </button>
      </div>

      {options.isLoading && <Loading what="the alternatives" />}
      {options.error && <Failed error={options.error} padded={false} />}
      {options.data && alternatives.length === 0 && (
        // Absence is absence, and informative: nothing else in this registry makes what this
        // step makes, which is why the resolver chose it.
        <p className="text-secondary text-ink-3 m-0">
          nothing else in this registry produces what this step produces.
        </p>
      )}

      <div className="flex flex-col gap-1">
        {alternatives.map((row) => (
          <button
            key={row.contract_id}
            type="button"
            data-testid="swap-option"
            data-active={chosen === row.contract_id || undefined}
            onClick={() => setChosen(row.contract_id)}
            className="text-left px-2 py-1.5 rounded-r border border-line bg-transparent
                       cursor-pointer data-[active]:border-line-2 data-[active]:bg-surface-2"
          >
            <span className="font-data text-body text-ink">{row.tool}</span>
            <span className="block text-secondary text-ink-3">{row.why}</span>
          </button>
        ))}
      </div>

      {chosen && (
        <div data-testid="consequences" className="border-t border-line pt-3">
          <p className="text-label uppercase tracking-[.13em] text-ink-3 m-0 mb-2">
            What changes
          </p>
          {would.isFetching && <Loading what="what would change" />}
          {would.data && added.length === 0 && fixed.length === 0 && (
            <p className="text-secondary text-ink-2 m-0">
              Nothing else. The graph validates the same either way.
            </p>
          )}
          {added.map((line) => (
            <p key={line} className="text-secondary text-[var(--undecided)] m-0">
              would break · <span className="font-data">{line}</span>
            </p>
          ))}
          {fixed.map((line) => (
            <p key={line} className="text-secondary text-pea m-0">
              would fix · <span className="font-data">{line}</span>
            </p>
          ))}

          {/* **Nothing is applied until this is pressed.** The preview above ran against a graph
              that exists only as an argument. */}
          <button
            type="button"
            data-testid="apply-swap"
            disabled={would.isFetching}
            onClick={() => onApply(chosen)}
            className="mt-3 px-3 py-1 rounded-r border border-[var(--link)] text-[var(--link)]
                       bg-transparent cursor-pointer text-body lift disabled:opacity-40"
          >
            Swap it
          </button>
        </div>
      )}
    </div>
  );
}
