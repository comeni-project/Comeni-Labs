import type { ReactNode } from "react";

const LABELS: Record<string, string> = {
  nf_process: "Process", nf_include: "Module file", roles: "Jobs", container: "Container",
  type_id: "Data type", format: "File formats", optional: "Optional", multiple: "Multiple files",
  via: "Passed through", key: "Destination", template: "Argument template", default: "Default",
  tier_hint: "Decision tier", domain: "Allowed values", min: "Minimum", max: "Maximum",
  states: "Declared states", states_required: "Required states", states_made: "States produced",
  states_conventional: "Conventional states", consumes: "Reads", produces: "Makes",
  inputs: "Inputs", expect: "Expected outputs", setup: "Setup commands", params: "Settings",
  when: "When", then: "Choose", because: "Reason", cite: "Reference", rows: "Ordered choices",
  decides: "Decides", effect: "Decision", of: "Job", when_implementation: "For tools",
  description: "Description", describes: "Describes", kind: "Kind", explain: "Meaning", pattern: "Output pattern",
  ports: "Ports", param: "Setting", value: "Value", name: "Name", id: "Identifier",
  priority: "Fallback priority", priority_because: "Fallback reason",
};
const label = (key: string) => LABELS[key] ?? key.replaceAll("_", " ");

/** Keep every declared field readable, including nested conditions and test setup. */
export function ValueDetails({ value }: { value: unknown }) {
  return <div className="text-[13px] leading-[1.55] [overflow-wrap:anywhere]">{renderValue(value)}</div>;
}

function renderValue(value: unknown, depth = 0): ReactNode {
  if (value === null || value === undefined) return <span className="text-ink-3">Not set</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "object") return <span className="whitespace-pre-wrap">{String(value) || "Empty text"}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-ink-3">None</span>;
    return <ol className="m-0 pl-5 list-decimal flex flex-col gap-2">{value.map((v, n) => <li key={n}>{renderValue(v, depth + 1)}</li>)}</ol>;
  }
  const fields = Object.entries(value as Record<string, unknown>).filter(([k]) => k !== "position");
  if (!fields.length) return <span className="text-ink-3">None</span>;
  return <dl className={`m-0 grid grid-cols-1 ${depth === 0 ? "sm:grid-cols-[minmax(0,110px)_minmax(0,1fr)]" : ""} gap-x-3 gap-y-2`}>
    {fields.map(([key, v]) => <div key={key} className="contents">
      <dt className="text-ink-3">{label(key)}</dt><dd className="m-0 min-w-0">{renderValue(v, depth + 1)}</dd>
    </div>)}
  </dl>;
}
