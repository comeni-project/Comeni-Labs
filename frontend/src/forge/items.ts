import type { components } from "../api/schema";

export type ItemView = components["schemas"]["ItemView"];
type Value = Record<string, unknown>;

export const valueOf = (item: ItemView): Value =>
  (item.value && typeof item.value === "object" && !Array.isArray(item.value) ? item.value : {}) as Value;

/** Removed items are gone from the tool: never drawn, never counted. */
export const live = (items: ItemView[]) => items.filter((i) => i.status !== "removed");

/** An AI proposal waiting for a person: what the Review list holds. */
export const waiting = (item: ItemView) => item.status === "proposed" || item.status === "reopened";

export const lastRevision = (item: ItemView) => item.revisions[item.revisions.length - 1];

/** Who made the item's current value: the AI's proposal, or a person's decision. */
export const byAi = (item: ItemView) => lastRevision(item)?.actor === "ai";

/** The AI's reason for its current proposal, when it gave one. */
export const reasonOf = (item: ItemView) => {
  const r = [...item.revisions].reverse().find((x) => x.actor === "ai" && x.because);
  return r?.because ?? null;
};

const after = (key: string, prefix: string) => key.slice(prefix.length);

/** What an item is, in a person's words: a title and the kind of part it belongs to. */
export function describe(item: ItemView): { title: string; kind: string; part: PartKind } {
  const k = item.key;
  const v = valueOf(item);
  if (k.startsWith("contract:input:")) return { title: after(k, "contract:input:"), kind: "Input", part: "port" };
  if (k.startsWith("contract:output:")) return { title: after(k, "contract:output:"), kind: "Output", part: "port" };
  if (k === "contract:process") return { title: "The process", kind: "Process", part: "process" };
  if (k === "contract:nf_inputs") return { title: "Input order", kind: "Process", part: "process" };
  if (k.startsWith("contract:constraint:")) return { title: item.sentence ?? "A constraint", kind: "Constraint", part: "process" };
  if (k.startsWith("parameters:param:")) return { title: String(v.name ?? after(k, "parameters:param:")), kind: "Parameter", part: "params" };
  if (k === "parameters:ext_args") return { title: "Extra arguments", kind: "Parameter", part: "params" };
  if (k === "parameters:none") return { title: "No parameters", kind: "Parameter", part: "params" };
  if (k.startsWith("rules:")) return { title: k === "rules:none" ? "No rule" : `Rule ${after(k, "rules:")}`, kind: "Rule", part: "rules" };
  if (k.startsWith("measurers:")) return { title: `Measurer ${after(k, "measurers:")}`, kind: "Measurer", part: "measurers" };
  if (k.startsWith("vocabulary:type:")) {
    const id = after(k, "vocabulary:type:");
    const states = Array.isArray(v.add_states) ? (v.add_states as string[]) : [];
    return states.length ? { title: `New state ${states.join(", ")}`, kind: `on ${id}`, part: "vocabulary" }
      : { title: `New data type ${id}`, kind: "Vocabulary", part: "vocabulary" };
  }
  if (k.startsWith("vocabulary:family:")) return { title: `New family ${after(k, "vocabulary:family:")}`, kind: "Vocabulary", part: "vocabulary" };
  if (k === "vocabulary:none") return { title: "No vocabulary change", kind: "Vocabulary", part: "vocabulary" };
  if (k.startsWith("tests:test:")) return { title: after(k, "tests:test:").replace(/_/g, " "), kind: "Test", part: "tests" };
  if (k === "questions:role") return { title: "Which job it does", kind: "Question", part: "process" };
  if (k === "questions:competition") return { title: "How the builder chooses it", kind: "Question", part: "rules" };
  if (k.startsWith("questions:input_type:")) return { title: `Data type of ${after(k, "questions:input_type:")}`, kind: "Question", part: "port" };
  if (k.startsWith("questions:output_type:")) return { title: `Data type of ${after(k, "questions:output_type:")}`, kind: "Question", part: "port" };
  return { title: k.split(":").slice(1).join(" "), kind: k.split(":")[0], part: "process" };
}

export type PartKind = "process" | "port" | "params" | "rules" | "measurers" | "vocabulary" | "tests";
