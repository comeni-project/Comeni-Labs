import { nameOf, type ItemView } from "../forging/useAdaptation";

export type Pin = { key: string; name: string; type: string | null };
export type ToolShape = { job: string | null; inputs: Pin[]; outputs: Pin[] };

const PREFIX = { inputs: "questions:input_type:", outputs: "questions:output_type:" };

function answer(item: ItemView): string | null {
  return (item.value as { choice?: string } | null)?.choice ?? null;
}

/** The tool as far as it is decided, from its questions: a pin for each input and output, with
 *  its type once answered, and the job. A removed question is no longer part of the tool. */
export function toolShape(items: ItemView[]): ToolShape {
  const live = items.filter((i) => i.status !== "removed");
  const pins = (prefix: string): Pin[] => live.filter((i) => i.key.startsWith(prefix))
    .map((i) => ({ key: i.key, name: nameOf(i.key), type: answer(i) }));
  const role = live.find((i) => i.key === "questions:role");
  return { job: role ? answer(role) : null, inputs: pins(PREFIX.inputs), outputs: pins(PREFIX.outputs) };
}
