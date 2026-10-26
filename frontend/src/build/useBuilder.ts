import type { DraftGraph, Step } from "../api/types";

/** A setting, plus whether the value on it is **this person's answer**.
 *
 * **It is not derivable from the tier, and that is the whole reason this type exists.** A tier-4
 * setting can hold a value nobody chose: the resolver's own tier-4 exit writes one and says so —
 * `selected the first of 1 candidates without judgement — please review`. So `tier === 4 &&
 * value !== null` does not mean *answered*, and the draft graph is the only place that knows
 * which values a person put there.
 *
 * The tier does **not** change (invariant 6: tier 4 is always flagged, even at high confidence).
 * What changes is what the interface may say about it — *this still needs a decision* is false
 * about a value somebody already decided, and it is the sentence the status line was making.
 */
export type Answered = Step["settings"][number] & { answered?: boolean };

/** A step whose settings carry that mark. `Step` is assignable to it, since `answered` is
 *  optional — so a caller with no draft in hand loses nothing. */
export type AnsweredStep = Omit<Step, "settings"> & { settings: Answered[] };

/** How many of a step's values **nobody has answered** — the count the red band and the status
 *  line both mean, and neither of them had. */
export function unanswered(steps: AnsweredStep[]): number {
  return steps.flatMap((step) => step.settings).filter(open).length;
}

/** Whether one value still **needs the person**: tier 4, not answered here, and not optional. */
export function open(setting: Answered): boolean {
  return setting.tier === 4 && !setting.answered && !setting.optional;
}

/** Whether one value is open but **optional**: left unset, the tool keeps its own behaviour, so it
 *  stays flagged for review without stopping a run (issue 384). The server says which (`optional`). */
export function optionalOpen(setting: Answered): boolean {
  return setting.tier === 4 && !setting.answered && !!setting.optional;
}

/** One step, with **what you have typed** laid over what the server last echoed back.
 *
 * `drawn` is a query keyed on the *debounced* graph and carries
 * `placeholderData: (previous) => previous`, so `step.settings[].value` deliberately lags an
 * edit — that is what keeps the canvas from blanking on every keystroke. A **controlled input**
 * fed from that lagging copy never advances between keys, so each `onChange` reads
 * `"" + newChar` and only the last character survives: typing `ILLUMINA` left `A`.
 *
 * **The graph is the authority for a value; the server is the authority for everything else**
 * — the tier, the domain, the reason. Overlaying only `value` keeps it that way, so a typed
 * value shows instantly while the tier it exits at stays the server's to stamp.
 */
export function withTypedValues(step: Step, graph: DraftGraph): AnsweredStep {
  const params = graph.nodes.find((node) => node.id === step.id)?.params;
  if (!params?.length) return step;
  // `DraftParam.value` admits `string | number | boolean` while a `SettingView` renders a
  // `string`. Everything a person types arrives as a string already; coercing here keeps the
  // widening in the graph, where the schema wants it, rather than in the control.
  const typed = new Map(params.map((param) => [param.name, String(param.value)]));
  return {
    ...step,
    settings: step.settings.map((setting) =>
      typed.has(setting.name)
        ? { ...setting, value: typed.get(setting.name)!, answered: true }
        : setting,
    ),
  };
}
