import type { Positions } from "../../build/geometry";
import { LivingCanvas } from "../../build/living/LivingCanvas";
import { Loading } from "../../ui/States";
import { progressOf, type RunNode } from "./model";
import { factsOf, useBuildCanvas, useReferences } from "./useRuns";

/** **The run, drawn on Build's canvas** (#511, `Run.dc.html`): the same steps where Build put them,
 *  each with how far it has got. Every run is drawn here, an earlier one too: a step it did not
 *  run shows as waiting. There is no other drawing of a run. */
export function RunCanvas({ draftId, nodes, samples, live, selected, onSelect, lit = null, focus = null, fit = true }: {
  draftId: string;
  runId: string;
  nodes: RunNode[];
  samples: number;
  live: boolean;
  selected: string | null;
  onSelect: (step: string | null) => void;
  /** Steps to light, the rest faded (Outputs: a file's way through the pipeline). */
  lit?: string[] | null;
  /** The step brought on screen when it changes. */
  focus?: string | null;
  /** Fit the whole drawing when it opens (Overview); Outputs opens at size, on `focus`. */
  fit?: boolean;
}) {
  const canvas = useBuildCanvas(draftId);
  const given = useReferences(draftId);
  if (canvas.isPending) return <Loading what="the pipeline" />;
  const frame = canvas.data?.canvas;
  if (!frame) return <p className="m-0 p-4 text-[13px] text-ink-3">The pipeline could not be drawn.</p>;
  const facts = factsOf(canvas.data);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const progress = Object.fromEntries(frame.steps.map((s) => [s.id, progressOf(byId[s.id], facts[s.id], samples, live)]));
  return (
    <LivingCanvas
      graph={frame.graph}
      positions={{ ...(canvas.data?.placement as Positions | undefined), ...(frame.placement as Positions | undefined) }}
      steps={Object.fromEntries(frame.steps.map((s) => [s.id, s]))}
      channels={frame.channels.map((channel) => channel.grain === "sample"
        ? { ...channel, count: samples } : channel)}
      authors={{}}
      selected={selected}
      onSelect={onSelect}
      samples={samples || undefined}
      progress={progress}
      animateProgress={live}
      given={given}
      lit={lit}
      focus={focus}
      fitOnOpen={fit}
    />
  );
}
