import { nameOf, type ItemView } from "../forging/useAdaptation";

export type Pin = {
  key: string; name: string; type: string | null; format?: string[];
  /** The process runs without this input (issue 460). */
  optional?: boolean;
  /** When a conditional output is written: "only with fasta". */
  only?: string;
};

type PortValue = { type_id?: string; format?: string[]; required?: boolean;
                   produced_when?: Record<string, unknown> | null };

/** A condition as a few words: `{given.fasta: present}` reads "only with fasta". */
export function onlyWith(when: Record<string, unknown> | null | undefined): string | undefined {
  if (!when || !Object.keys(when).length) return undefined;
  const parts = Object.entries(when).map(([key, value]) => {
    const name = key.slice(key.indexOf(".") + 1);
    return key.startsWith("given.") || value === true ? name : `${name} = ${JSON.stringify(value)}`;
  });
  return `only with ${parts.join(" and ")}`;
}

function portParts(port: PortValue | undefined): Pick<Pin, "format" | "optional" | "only"> {
  const only = onlyWith(port?.produced_when);
  return {
    ...(port?.format?.length ? { format: port.format } : {}),
    ...(port?.required === false ? { optional: true } : {}),
    ...(only ? { only } : {}),
  };
}
export type ToolShape = { job: string | null; inputs: Pin[]; outputs: Pin[] };

const PREFIX = { inputs: "questions:input_type:", outputs: "questions:output_type:" };

function answer(item: ItemView): string | null {
  return (item.value as { choice?: string } | null)?.choice ?? null;
}

/** The tool as far as it is decided, from its questions: a pin for each input and output, with
 *  its type once answered, and the job. A removed question or contract port is no longer part
 *  of the tool. */
export function toolShape(items: ItemView[]): ToolShape {
  const live = items.filter((i) => i.status !== "removed");
  const pins = (prefix: string): Pin[] => {
    const contractPrefix = prefix === PREFIX.inputs ? "contract:input:" : "contract:output:";
    // A port the contract removed is gone, though its question keeps its answer (issue 467).
    const removed = new Set(items.filter((i) => i.status === "removed"
      && i.key.startsWith(contractPrefix)).map((i) => nameOf(i.key)));
    const questions = live.filter((i) => i.key.startsWith(prefix) && !removed.has(nameOf(i.key)));
    const result = questions.map((i) => {
      const port = live.find((p) => p.key === `${contractPrefix}${nameOf(i.key)}`);
      return { key: i.key, name: nameOf(i.key), type: answer(i), ...portParts(port?.value as PortValue) };
    });
    // Re-forging begins with a declared contract, before its questions are drafted.
    for (const port of live.filter((i) => i.key.startsWith(contractPrefix))) {
      const name = nameOf(port.key);
      if (items.some((i) => i.key === `${prefix}${name}`)) continue;
      const value = port.value as PortValue;
      if (value?.type_id) result.push({ key: port.key, name, type: value.type_id, ...portParts(value) });
    }
    return result;
  };
  const role = live.find((i) => i.key === "questions:role");
  return { job: role ? answer(role) : (live.find((i) => i.key === "contract:process")?.value as { roles?: string[] } | undefined)?.roles?.join(", ") || null, inputs: pins(PREFIX.inputs), outputs: pins(PREFIX.outputs) };
}
