import type { Positions } from "../../build/geometry";
import { LivingCanvas } from "../../build/living/LivingCanvas";
import { Loading } from "../../ui/States";
import { Graph } from "./Graph";
import { progressOf, type RunNode } from "./model";
import { factsOf, useBuildCanvas, useReferences } from "./useRuns";

/** **The run, drawn on Build's canvas** (#511, `Run.dc.html`): the same steps where Build put them,
 *  each with how far it has got. A run of a pipeline the analysis no longer keeps is drawn from
 *  the run's own record instead, since Build's canvas is of the current one. */
export function RunCanvas({ draftId, runId, nodes, samples, live, current, selected, onSelect, lit = null, focus = null }: {
  draftId: string;
  runId: string;
  nodes: RunNode[];
  samples: number;
  live: boolean;
  /** Whether this run is of the pipeline the analysis keeps now. */
  current: boolean;
  selected: string | null;
  onSelect: (step: string | null) => void;
  /** Steps to light, the rest faded (Outputs: a file's way through the pipeline). */
  lit?: string[] | null;
  /** The step brought on screen when it changes. */
  focus?: string | null;
}) {
  const canvas = useBuildCanvas(draftId);
  const given = useReferences(draftId);
  if (!current) return <Graph runId={runId} />;
  if (canvas.isPending) return <Loading what="the pipeline" />;
  const frame = canvas.data?.canvas;
  if (!frame) return <Graph runId={runId} />;
  const facts = factsOf(canvas.data);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const progress = Object.fromEntries(frame.steps.map((s) => [s.id, progressOf(byId[s.id], facts[s.id], samples, live)]));
  return (
    <LivingCanvas
      graph={frame.graph}
      positions={{ ...(canvas.data?.placement as Positions | undefined), ...(frame.placement as Positions | undefined) }}
      steps={Object.fromEntries(frame.steps.map((s) => [s.id, s]))}
      channels={frame.channels}
      authors={{}}
      selected={selected}
      onSelect={onSelect}
      samples={samples || undefined}
      progress={progress}
      given={given}
      lit={lit}
      focus={focus}
      fitOnOpen
    />
  );
}
