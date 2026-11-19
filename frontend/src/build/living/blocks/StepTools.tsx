import { useState } from "react";

import type { DraftGraph, Step } from "../../../api/types";
import { feedingOnly, withContract, withoutNode, withParam } from "../../graphOps";
import { Settings } from "../../Settings";
import { Swap } from "../../Swap";
import { withTypedValues } from "../../useBuilder";
import { processName } from "../format";
import { BlockFrame, Primary, Secondary } from "./parts";

type Value = string | number | boolean | null;

/** What a person can do to a step that is already drawn: swap it, set its values, remove it.
 *
 * Opened from a step's card beside it on the canvas (#499). The manual builder's `Swap` and
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
type Mode = "menu" | "swap" | "settings" | "remove";

export function StepTools({
  node,
  step,
  graph,
  onEdit,
  start = "menu",
  onDone,
}: {
  node: string;
  /** The drawn view of this step — its ports and settings. Absent until the server has drawn it. */
  step: Step | undefined;
  graph: DraftGraph;
  onEdit: (graph: DraftGraph) => void;
  /** Open straight on one tool, as a step's card does (#499); `onDone` then closes the card. */
  start?: Mode;
  onDone?: () => void;
}) {
  const [mode, setMode] = useState<Mode>(start);
  const [answers, setAnswers] = useState<Record<string, Value>>({});
  const name = processName(node);
  const label = `change ${name}`;
  const answered = (g: DraftGraph) =>
    Object.entries(answers).reduce((acc, [setting, value]) => withParam(acc, node, setting, value), g);
  const back = () => {
    setAnswers({});
    if (start !== "menu" && onDone) onDone();
    else setMode("menu");
  };

  if (mode === "swap" && step) {
    return (
      <BlockFrame label={`swap ${name}`} title={`swap ${name}`}>
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
        label={`values for ${name}`}
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
    // The rebuild drops what only fed it; said here, so it is not a surprise (#509).
    const along = feedingOnly(graph, node).map(processName);
    return (
      <BlockFrame
        label={`remove ${name}`}
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
          {along.length > 0 && `${along.join(", ")} only ${along.length === 1 ? "feeds" : "feed"} ${name}, so ${along.length === 1 ? "it goes" : "they go"} too. `}
          The log records it as yours.
        </p>
      </BlockFrame>
    );
  }

  // **Only the three verbs**: the opened step's name and tool head the panel above this.
  return (
    <section aria-label={label} className="flex flex-wrap items-center gap-2">
      <Secondary disabled={!step} onClick={() => setMode("swap")}>Swap for something else</Secondary>
      <Secondary disabled={!step} onClick={() => setMode("settings")}>Settings</Secondary>
      <Secondary onClick={() => setMode("remove")}>Remove</Secondary>
      {!step && <span className="text-[12.5px] text-ink-3">drawing…</span>}
    </section>
  );
}
