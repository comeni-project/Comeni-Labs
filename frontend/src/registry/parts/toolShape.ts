import { nameOf, type ItemView } from "../forging/useAdaptation";

export type Pin = { key: string; name: string; type: string | null; format?: string[] };
export type ToolShape = { job: string | null; inputs: Pin[]; outputs: Pin[] };

const PREFIX = { inputs: "questions:input_type:", outputs: "questions:output_type:" };

function answer(item: ItemView): string | null {
  return (item.value as { choice?: string } | null)?.choice ?? null;
}

/** The tool as far as it is decided, from its questions: a pin for each input and output, with
 *  its type once answered, and the job. A removed question is no longer part of the tool. */
export function toolShape(items: ItemView[]): ToolShape {
  const live = items.filter((i) => i.status !== "removed");
  const pins = (prefix: string): Pin[] => {
    const contractPrefix = prefix === PREFIX.inputs ? "contract:input:" : "contract:output:";
    const questions = live.filter((i) => i.key.startsWith(prefix));
    const result = questions.map((i) => {
      const port = live.find((p) => p.key === `${contractPrefix}${nameOf(i.key)}`);
      const format = (port?.value as { format?: string[] } | undefined)?.format;
      return { key: i.key, name: nameOf(i.key), type: answer(i), ...(format?.length ? { format } : {}) };
    });
    // Re-forging begins with a declared contract, before its questions are drafted.
    for (const port of live.filter((i) => i.key.startsWith(contractPrefix))) {
      const name = nameOf(port.key);
      if (items.some((i) => i.key === `${prefix}${name}`)) continue;
      const value = port.value as { type_id: string; format?: string[] };
      if (value?.type_id) result.push({ key: port.key, name, type: value.type_id,
        ...(value.format?.length ? { format: value.format } : {}) });
    }
    return result;
  };
  const role = live.find((i) => i.key === "questions:role");
  return { job: role ? answer(role) : (live.find((i) => i.key === "contract:process")?.value as { roles?: string[] } | undefined)?.roles?.join(", ") || null, inputs: pins(PREFIX.inputs), outputs: pins(PREFIX.outputs) };
}
