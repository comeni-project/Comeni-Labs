import { useId, useState } from "react";

import { Failed } from "../../ui/States";
import { RegistryPicker, type PickerEntry } from "../parts/RegistryPicker";
import { roleEntries, typeEntries, useChoices } from "../parts/useChoices";

/** The command model's JSON Schema. Rendering fields never replaces server validation. */
export type Schema = {
  $ref?: string; $defs?: Record<string, Schema>; title?: string; description?: string;
  type?: string; properties?: Record<string, Schema>; required?: string[];
  anyOf?: Schema[]; enum?: (string | number)[]; const?: unknown; default?: unknown;
  items?: Schema; additionalProperties?: Schema | boolean;
  minimum?: number; maximum?: number; minLength?: number; maxLength?: number;
};
export type Value = unknown;
const input = "w-full min-w-0 bg-surface text-ink font-data text-[13px] p-2 border border-line-2 rounded-control";
const labels: Record<string, string> = {
  nf_process: "Process name", nf_include: "Module path", type_id: "Content type",
  via: "Pass through", key: "Extension key", because: "Reason", position: "Position (from zero)",
  nf_inputs: "Process inputs", ext_args: "Baseline arguments", tier_hint: "Decision tier",
  add_states: "States to add", state_required: "Required states", state: "States",
  decides: "What the rule decides", of: "Job", when: "When", then: "Use this value",
  expect: "Expected outputs", inputs: "Inputs", template: "Argument template",
  choice: "Answer", new: "Propose new vocabulary", format: "File formats",
};
export function labelOf(name: string): string {
  return labels[name] ?? name.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
}
export function resolve(schema: Schema, root: Schema): Schema {
  return schema.$ref ? root.$defs?.[schema.$ref.split("/").at(-1)!] ?? schema : schema;
}
function matches(s: Schema, v: unknown, root: Schema): boolean {
  s = resolve(s, root);
  if (s.anyOf) return s.anyOf.some((b) => matches(b, v, root));
  if (s.type === "null") return v === null;
  if (s.type === "array") return Array.isArray(v);
  if (s.type === "object") return !!v && typeof v === "object" && !Array.isArray(v)
    && (s.required ?? []).every((k) => k in (v as object))
    && (s.additionalProperties !== false || Object.keys(v as object).every((k) => k in (s.properties ?? {})));
  if (s.type === "integer") return typeof v === "number" && Number.isInteger(v);
  return typeof v === s.type;
}
export function initial(schema: Schema, root: Schema): unknown {
  const s = resolve(schema, root);
  if (s.default !== undefined && s.default !== null) return structuredClone(s.default);
  if (s.const !== undefined) return s.const;
  if (s.enum) return s.enum[0];
  if (s.anyOf) return initial(s.anyOf.find((b) => resolve(b, root).type !== "null") ?? s.anyOf[0], root);
  if (s.type === "object") return Object.fromEntries((s.required ?? [])
    .map((k) => [k, initial(s.properties?.[k] ?? {}, root)]));
  if (s.type === "array") return [];
  if (s.type === "boolean") return false;
  if (s.type === "integer" || s.type === "number") return s.minimum ?? 0;
  if (s.type === "null") return null;
  return "";
}

type Reference = "type" | "role" | "tool";
export function RegistryReference({ kind, value, onChange }: {
  kind: Reference; value: string; onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const choices = useChoices(open);
  const entries: PickerEntry[] = !choices.data ? [] : kind === "type" ? typeEntries(choices.data)
    : kind === "role" ? roleEntries(choices.data) : choices.data.tools.map((t) => ({
      id: t.id, name: t.id, group: t.id.split("/")[0], says: t.roles.join(", "),
      before: t.reads, after: t.makes,
    }));
  return <div className="flex flex-col gap-1 min-w-0">
    <button type="button" className="control" onClick={() => setOpen(true)}>Choose {kind} from the registry</button>
    {open && choices.isError && <Failed error={choices.error} padded={false} />}
    {open && choices.data && <div className="picker-anchor">
      <button type="button" className="picker-outside" aria-label="Close the registry picker" onClick={() => setOpen(false)} />
      <RegistryPicker title={`Choose a ${kind}`} entries={entries}
      chosen={value.split("::")[0]} before={kind === "type" ? "Made by" : "Reads"}
      after={kind === "type" ? "Read by" : "Makes"} onClose={() => setOpen(false)}
      onPick={(v) => { onChange(v); setOpen(false); }} /></div>}
  </div>;
}

export function referenceFor(name: string, family: string): Reference | undefined {
  if (["type_id", "describes"].includes(name)) return "type";
  if (["roles", "of"].includes(name)) return "role";
  if (["tool", "when_implementation"].includes(name)) return "tool";
  if (name === "choice") return family === "questions:role" ? "role"
    : /questions:(input|output)_type/.test(family) ? "type" : undefined;
}

/** Repeating fields preserve their order; maps expose each name and value separately. */
export function Fields({ schema, root, value, onChange, label, reference, family = "", path = "" }: {
  schema: Schema; root: Schema; value: Value; onChange: (v: Value) => void;
  label: string; reference?: Reference; family?: string; path?: string;
}) {
  const id = useId();
  const s = resolve(schema, root);
  const branches = s.anyOf;
  const [branch, setBranch] = useState<number | null>(null);
  const variants = branches ?? (!s.type && !s.enum && s.const === undefined ? [
    { type: "string", title: "Text" }, { type: "integer", title: "Integer" },
    { type: "number", title: "Number" }, { type: "boolean", title: "Yes or no" },
    { type: "null", title: "No value" },
    { type: "array", title: "List", items: {} },
    { type: "object", title: "Named values", additionalProperties: {} },
  ] as Schema[] : undefined);
  const concrete = branches?.filter((b) => resolve(b, root).type !== "null");
  if (concrete?.length === 1 && concrete.length !== branches!.length) {
    if (value == null) return <button type="button" className="control self-start"
      onClick={() => onChange(initial(concrete[0], root))}>Set {label.toLowerCase()}</button>;
    return <Fields schema={concrete[0]} root={root} value={value} onChange={onChange}
      label={label} reference={reference} family={family} path={path} />;
  }
  if (variants) {
    const best = variants.map((b, n) => ({ n, schema: resolve(b, root) }))
      .filter((b) => matches(b.schema, value, root))
      .sort((a, b) => (b.schema.required?.length ?? 0) - (a.schema.required?.length ?? 0))[0]?.n ?? 0;
    const chosen = branch ?? best;
    return <fieldset className="min-w-0 border-0 m-0 p-0 flex flex-col gap-2">
      <legend className="text-[12.5px] text-ink-2">{label}</legend>
      <select aria-label={`${label} kind`} className={input} value={chosen} onChange={(e) => {
        const n = Number(e.target.value); setBranch(n); onChange(initial(variants[n], root));
      }}>{variants.map((b, n) => {
        const r = resolve(b, root);
        return <option key={n} value={n}>{r.title ?? (r.type === "null" ? "Not set" : labelOf(r.type ?? "value"))}</option>;
      })}</select>
      <Fields key={chosen} schema={variants[chosen]} root={root} value={value} onChange={onChange}
        label={label} reference={reference} family={family} path={path} />
    </fieldset>;
  }
  if (s.type === "null") return null;
  if (s.type === "object") {
    const object = (value && typeof value === "object" && !Array.isArray(value) ? value : {}) as Record<string, Value>;
    const properties = s.properties ?? {};
    const dynamic = s.additionalProperties && typeof s.additionalProperties === "object" ? s.additionalProperties : null;
    return <fieldset className="min-w-0 border border-line-soft rounded-control p-3 m-0 flex flex-col gap-3">
      <legend className="text-[13px] text-ink-2 px-1">{label}</legend>
      {Object.entries(properties).map(([name, field]) => {
        const required = s.required?.includes(name);
        const present = name in object;
        return <div key={name} className="min-w-0 flex flex-col gap-1">
          {present || required ? <>
            <Fields schema={field} root={root} value={object[name]} label={labelOf(name)} family={family}
              path={`${path}.${name}`} reference={referenceFor(name, family)}
              onChange={(v) => onChange({ ...object, [name]: v })} />
            {!required && <button type="button" className="text-[12px] text-ink-3 self-start underline" onClick={() => {
              const next = { ...object }; delete next[name]; onChange(next);
            }}>Leave {labelOf(name).toLowerCase()} unset</button>}
          </> : <button type="button" className="control self-start" onClick={() =>
            onChange({ ...object, [name]: initial(field, root) })}>Add {labelOf(name).toLowerCase()}</button>}
        </div>;
      })}
      {dynamic && <MapFields value={object} schema={dynamic} root={root} label={label} family={family} onChange={onChange} />}
    </fieldset>;
  }
  if (s.type === "array") {
    const list = Array.isArray(value) ? value : [];
    return <fieldset className="min-w-0 border border-line-soft rounded-control p-3 m-0 flex flex-col gap-2">
      <legend className="text-[13px] text-ink-2 px-1">{label}</legend>
      {list.map((v, n) => <div key={n} className="min-w-0 flex flex-col gap-1">
        <Fields schema={s.items ?? {}} root={root} value={v} label={`${label} ${n + 1}`} family={family}
          reference={reference} path={path} onChange={(next) => onChange(list.map((old, i) => i === n ? next : old))} />
        <button type="button" className="control self-start" onClick={() => onChange(list.filter((_, i) => i !== n))}>Remove {label.toLowerCase()} {n + 1}</button>
      </div>)}
      <button type="button" className="control self-start" onClick={() => onChange([...list, initial(s.items ?? {}, root)])}>Add {label.toLowerCase()}</button>
    </fieldset>;
  }
  return <div className="min-w-0 flex flex-col gap-1">
    <label htmlFor={id} className="text-[12.5px] text-ink-2">{label}</label>
    {s.enum ? <select id={id} className={input} value={String(value ?? s.enum[0])}
      onChange={(e) => onChange(s.enum!.find((v) => String(v) === e.target.value))}>
      {s.enum.map((v) => <option key={v} value={v}>{v}</option>)}</select>
    : s.type === "boolean" ? <select id={id} className={input} value={value ? "true" : "false"}
      onChange={(e) => onChange(e.target.value === "true")}><option value="false">No</option><option value="true">Yes</option></select>
    : <input id={id} className={input} type={s.type === "number" || s.type === "integer" ? "number" : "text"}
      step={s.type === "integer" ? 1 : "any"} min={s.minimum} max={s.maximum} maxLength={s.maxLength}
      value={value == null ? "" : String(value)} onChange={(e) => onChange(e.target.type === "number"
        ? e.target.value === "" ? "" : Number(e.target.value) : e.target.value)} />}
    {reference && <RegistryReference kind={reference} value={String(value ?? "")} onChange={onChange} />}
  </div>;
}

function MapFields({ value, schema, root, label, family, onChange }: {
  value: Record<string, Value>; schema: Schema; root: Schema; label: string; family: string;
  onChange: (v: Value) => void;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  return <>
    {Object.entries(value).map(([key, v]) => <div key={key} className="min-w-0 flex flex-col gap-1">
      <Fields schema={schema} root={root} value={v} label={key} family={family}
        onChange={(next) => onChange({ ...value, [key]: next })} />
      <button type="button" className="control self-start" onClick={() => {
        const next = { ...value }; delete next[key]; onChange(next);
      }}>Remove {key}</button>
    </div>)}
    <label className="text-[12.5px] text-ink-2">New {label.toLowerCase()} name
      <input className={input} value={name} onChange={(e) => setName(e.target.value)} />
    </label>
    <button type="button" className="control self-start" onClick={() => {
      if (!name.trim()) { setError("Give this entry a name."); return; }
      if (Object.hasOwn(value, name.trim())) { setError("That name is already in use."); return; }
      onChange({ ...value, [name.trim()]: initial(schema, root) }); setName(""); setError("");
    }}>Add named value</button>
    {error && <p role="alert" className="text-needs-you-ink m-0">{error}</p>}
  </>;
}
