import { Fields, resolve, type Schema } from "./ConstructorFields";

/** Preview the declared argument text; the server still checks the route and domain. */
export function SettingFields({ schema, value, onChange }: {
  schema: Schema; value: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void;
}) {
  const domain = value.domain as { kind?: string; values?: string[]; minimum?: number; maximum?: number } | null;
  const kind = domain?.kind ?? (typeof value.default === "boolean" ? "boolean"
    : typeof value.default === "number" ? Number.isInteger(value.default) ? "integer" : "number" : "text");
  const declaredDomain = schema.properties!.domain;
  const domainSchema = resolve(declaredDomain.anyOf?.find((b) => resolve(b, schema).type === "object") ?? declaredDomain, schema);
  const domainProperties = Object.fromEntries(Object.entries(domainSchema.properties ?? {})
    .filter(([name]) => kind === "enum" ? name === "values" : ["minimum", "maximum"].includes(name)));
  const properties = { ...schema.properties }; delete properties.default; delete properties.domain;
  const change = (next: unknown) => {
    const changed = next as Record<string, unknown>;
    if (changed.via !== value.via) { delete changed.key; delete changed.template; }
    if (changed.key !== value.key && !["args", "args2", "args3"].includes(String(changed.key))) delete changed.template;
    onChange(changed);
  };
  const preview = value.default == null ? "No declared default; resolution must supply an answer or leave it to the tool where allowed."
    : value.via === "ext" && ["args", "args2", "args3"].includes(String(value.key))
      ? value.template ? String(value.template).replaceAll("{value}", String(value.default))
        : "Add an argument template containing {value}."
      : `${value.via === "ext" ? `ext.${value.key ?? "?"}` : value.via === "meta" ? `meta.${value.name}`
        : value.via === "positional" ? `positional input ${value.name}` : value.name} = ${String(value.default)}`;
  return <div className="flex flex-col gap-3 min-w-0">
    <label className="text-[12.5px] text-ink-2">Setting kind
      <select className="control w-full" value={kind} onChange={(e) => {
        const k = e.target.value;
        onChange({ ...value, domain: k === "text" ? null : { kind: k, ...(k === "enum" ? { values: [] } : {}) },
          default: null });
      }}>{["text", "integer", "number", "boolean", "enum"].map((k) =>
        <option key={k} value={k}>{k === "boolean" ? "Yes or no" : k === "enum" ? "One of a list" : k}</option>)}</select>
    </label>
    {["integer", "number", "enum"].includes(kind) && <Fields schema={{ ...domainSchema, properties: domainProperties, required: [] }}
      root={schema} value={domain ?? { kind }} label="Legal values"
      onChange={(next) => onChange({ ...value, domain: { ...(next as object), kind } })} />}
    <label className="text-[12.5px] text-ink-2 flex gap-2 items-center">
      <input type="checkbox" checked={value.default != null} onChange={(e) => onChange({ ...value,
        default: !e.target.checked ? null : kind === "boolean" ? false : ["integer", "number"].includes(kind) ? 0
          : kind === "enum" ? domain?.values?.[0] ?? "" : "" })} />Declare a default
    </label>
    {value.default != null && <Fields schema={kind === "enum" && domain?.values?.length
      ? { type: "string", enum: domain.values } : { type: kind === "enum" || kind === "text" ? "string" : kind, minimum: domain?.minimum, maximum: domain?.maximum }}
      root={schema} value={value.default} label="Default" onChange={(next) => onChange({ ...value, default: next })} />}
    <Fields schema={{ ...schema, properties }} root={schema} value={value} onChange={change} label="Setting" />
    <output aria-label="Setting preview" className="block min-w-0 break-words bg-paper-2 border border-line-soft rounded-control p-3 font-data text-[13px]">
      <span className="block text-ink-3 text-[12px]">Declared setting preview</span>{preview}
    </output>
  </div>;
}
