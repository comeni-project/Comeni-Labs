import { useState } from "react";

import type { DraftGraph, Step } from "../../../api/types";
import { withContract, withoutNode, withParam } from "../../graphOps";
import { Settings } from "../../Settings";
import { Swap } from "../../Swap";
import { withTypedValues } from "../../useBuilder";
import { processName } from "../format";
import { BlockFrame, Primary, Secondary } from "./parts";

type Value = string | number | boolean | null;

/** What a person can do to a step that is already drawn: swap it, set its values, remove it.
 *
 * **Still no inspector.** This is a block in the conversation, opened by selecting the step and
 * drawn under the line that says who decided it — the log stays the one place a step is
 * explained, and now it is also where a step is changed by hand. The manual builder's `Swap` and
 * `Settings` are reused rather than redrawn, so the consequences shown before a swap and the bands
 * a value sits in are the same code on both builders.
 *
 * **Every change leaves as one whole graph through `onEdit`**, which is the session's edit verb:
 * the server composes the receipt, moves the revision and restamps only the decision that changed
 * — a swap restamps *which contract*, not *whether this step exists*.
 *
 * **Values are staged, then sent once.** `Settings` reports every keystroke, and the manual builder
 * debounces its saves; here each call is a revision and a receipt, so typing `ILLUMINA` straight
 * through would write eight lines to the log and stale the step on offer eight times. What is
 * staged is the *answers*, not a copy of the graph, so they are laid over whatever graph is
 * current when the person presses — a poll that moved the draft meanwhile is not overwritten.
 */
export function StepTools({
  node,
  step,
  graph,
  onEdit,
}: {
  node: string;
  /** The drawn view of this step — its ports and settings. Absent until the server has drawn it. */
  step: Step | undefined;
  graph: DraftGraph;
  onEdit: (graph: DraftGraph) => void;
}) {
  const [mode, setMode] = useState<"menu" | "swap" | "settings" | "remove">("menu");
  const [answers, setAnswers] = useState<Record<string, Value>>({});
  const name = processName(node);
  const label = `change ${name}`;
  const answered = (g: DraftGraph) =>
    Object.entries(answers).reduce((acc, [setting, value]) => withParam(acc, node, setting, value), g);
  const back = () => {
    setAnswers({});
    setMode("menu");
  };

  if (mode === "swap" && step) {
    return (
      <BlockFrame label={label} title={`swap ${name}`}>
        <Swap
          step={step}
          graph={graph}
          onClose={back}
          onApply={(contract) => {
            onEdit(withContract(graph, node, contract));
            back();
          }}
        />
      </BlockFrame>
    );
  }

  if (mode === "settings" && step) {
    const staged = Object.keys(answers).length;
    return (
      <BlockFrame
        label={label}
        title={`values for ${name}`}
        aside={staged ? `${staged} not yet sent` : undefined}
        actions={
          <>
            <Primary disabled={staged === 0} onClick={() => { onEdit(answered(graph)); back(); }}>
              Use these values
            </Primary>
            <Secondary onClick={back}>Cancel</Secondary>
          </>
        }
      >
        <Settings
          step={withTypedValues(step, answered(graph))}
          onClose={back}
          onSet={(setting, value) => setAnswers((was) => ({ ...was, [setting]: value }))}
        />
      </BlockFrame>
    );
  }

  if (mode === "remove") {
    const wires = graph.edges.filter((e) => e.from_node === node || e.to_node === node).length;
    return (
      <BlockFrame
        label={label}
        title={`remove ${name}`}
        actions={
          <>
            <Primary onClick={() => { onEdit(withoutNode(graph, node)); back(); }}>
              {`Remove ${name}`}
            </Primary>
            <Secondary onClick={back}>Keep it</Secondary>
          </>
        }
      >
        <p className="m-0 text-[12.5px] leading-[1.6] text-ink">
          {wires === 0
            ? `${name} has no wires.`
            : `The ${wires === 1 ? "wire" : `${wires} wires`} into and out of ${name} go with it.`}{" "}
          The log records it as yours.
        </p>
      </BlockFrame>
    );
  }

  const contract = graph.nodes.find((n) => n.id === node)?.contract_id ?? "";
  return (
    <BlockFrame
      label={label}
      title={name}
      aside={step ? undefined : "drawing…"}
      actions={
        <>
          <Secondary disabled={!step} onClick={() => setMode("swap")}>Swap for something else</Secondary>
          <Secondary disabled={!step} onClick={() => setMode("settings")}>Settings</Secondary>
          <Secondary onClick={() => setMode("remove")}>Remove</Secondary>
        </>
      }
    >
      <p className="m-0 font-data text-[11px] text-ink-3">{contract}</p>
    </BlockFrame>
  );
}
