import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { get } from "../../api/client";
import { Failed } from "../../ui/States";
import { Fields, initial, RegistryReference, resolve, type Schema } from "./ConstructorFields";
import { SettingFields } from "./SettingFields";
import type { ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

export type ConstructorKind = { family: string; label: string; named: boolean; fields: Schema };
export type Constructors = { kinds: ConstructorKind[]; inputs: string[]; outputs: string[] };
type Actions = ReturnType<typeof useForgeActions>;

function familyOf(key: string): string {
  return key.split(":").slice(0, 2).join(":");
}

export function ItemConstructor({ id, piece, items, item, actions, onCancel }: {
  id: string; piece: string; items: ItemView[]; item?: ItemView; actions: Actions; onCancel?: () => void;
}) {
  const forms = useQuery({ queryKey: ["forge-constructors", id],
    queryFn: () => get<Constructors>(`/forge/adaptations/${id}/constructors`) });
  if (forms.isError) return <Failed error={forms.error} padded={false} />;
  if (!forms.data) return <p role="status">Loading fields…</p>;
  return <Constructor key={item?.key ?? piece} forms={forms.data} piece={piece} items={items}
    item={item} actions={actions} onCancel={onCancel} />;
}

function withoutIdentity(schema: Schema, root: Schema, identity: string): Schema {
  const s = resolve(schema, root);
  if (s.anyOf) return { ...s, anyOf: s.anyOf.map((b) => withoutIdentity(b, root, identity)) };
  return { ...s, properties: s.properties
    ? Object.fromEntries(Object.entries(s.properties).filter(([key]) => key !== identity)) : undefined,
    required: s.required?.filter((key) => key !== identity), additionalProperties: true };
}

function Constructor({ forms, piece, items, item, actions, onCancel }: {
  forms: Constructors; piece: string; items: ItemView[]; item?: ItemView; actions: Actions; onCancel?: () => void;
}) {
  const listId = useId().replaceAll(":", "");
  const [expected, setExpected] = useState(item?.current_n);
  const kinds = forms.kinds.filter((k) => k.family.startsWith(`${piece}:`));
  const [family, setFamily] = useState(item ? familyOf(item.key) : kinds[0]?.family ?? "");
  const kind = kinds.find((k) => k.family === family);
  const [name, setName] = useState(item && kind?.named ? item.key.split(":").slice(2).join(":") : "");
  const [value, setValue] = useState<unknown>(item?.value ?? (kind ? initial(kind.fields, kind.fields) : {}));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [saving, setSaving] = useState(false);
  if (!kind) return <p role="alert">No constructor is available for this item.</p>;
  const hints = family.endsWith("input_type") || family === "contract:input" ? forms.inputs
    : family.endsWith("output_type") || family === "contract:output" ? forms.outputs : [];
  const record = (value && typeof value === "object" && !Array.isArray(value) ? value : {}) as Record<string, unknown>;
  const hasIdentity = ["contract:input", "contract:output", "parameters:param",
    "vocabulary:type", "vocabulary:measurement", "vocabulary:role", "vocabulary:family"].includes(family);
  const identity = ["vocabulary:type", "vocabulary:measurement", "vocabulary:family"].includes(family) ? "id" : "name";
  const changeName = (next: string) => {
    setName(next); setSaved("");
    if (hasIdentity) {
      setValue({ ...record, [identity]: next });
    }
  };
  const updateValue = (next: unknown) => {
    setSaved("");
    setValue(hasIdentity && next && typeof next === "object" && !Array.isArray(next)
      ? { ...next, [identity]: name } : next);
  };
  const fields = kind.named ? withoutIdentity(kind.fields, kind.fields, identity) : kind.fields;
  return <form aria-label={item ? `Change ${name || kind.label}` : "Write an item"}
    className="min-w-0 flex flex-col gap-3" onSubmit={async (e) => {
      e.preventDefault(); setError(""); setSaved("");
      if (kind.named && !name.trim()) { setError("Give this item a name."); return; }
      const key = kind.named ? `${family}:${name.trim()}` : family;
      const existing = items.find((i) => i.key === key);
      if (!item && existing) { setError("This item already exists. Edit it above."); return; }
      setSaving(true);
      try {
        const result = await actions.command.mutateAsync({ move: piece === "questions" ? "answer" : item ? "change" : "write",
          item: key, expected, value: hasIdentity ? { ...record, [identity]: name.trim() } : value });
        if (item) setExpected(result?.items?.find((i) => i.key === key)?.current_n ?? expected);
        setSaved(`Saved ${name.trim() || kind.label}.`);
        if (!item) { setName(""); setValue(initial(kind.fields, kind.fields)); }
      } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
      finally { setSaving(false); }
    }}>
    <fieldset disabled={saving} className="min-w-0 border-0 m-0 p-0 flex flex-col gap-3">
      <label className="text-[12.5px] text-ink-2">What are you adding?
        <select className="control w-full" disabled={!!item} value={family} onChange={(e) => {
          const next = kinds.find((k) => k.family === e.target.value)!;
          setFamily(next.family); setName(""); setValue(initial(next.fields, next.fields)); setError(""); setSaved("");
        }}>{kinds.map((k) => <option key={k.family} value={k.family}>{k.label}</option>)}</select>
      </label>
      {kind.named && <label className="text-[12.5px] text-ink-2">{family === "vocabulary:family" ? "Family ID" : hints.length ? "Module channel" : "Item name"}
        <input className="control w-full font-data" value={name} disabled={!!item} list={`channels-${listId}`}
          onChange={(e) => changeName(e.target.value)} />
        <datalist id={`channels-${listId}`}>{hints.map((n) => <option key={n} value={n} />)}</datalist>
      </label>}
      {family === "vocabulary:family" && <p className="m-0 text-[12.5px] text-ink-2">
        Use the first part of the type ID: assembly.fasta belongs to assembly. Describe what the family holds in at most 200 characters.
      </p>}
      {(family === "vocabulary:type" || family === "vocabulary:role") && !item &&
        <RegistryReference kind={family === "vocabulary:type" ? "type" : "role"} value={name} onChange={changeName} />}
      {family === "parameters:param" ? <SettingFields schema={fields} value={record} onChange={updateValue} />
        : <Fields schema={fields} root={kind.fields} value={value} onChange={updateValue} label={kind.label} family={family} />}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="control-primary" disabled={saving} aria-busy={saving}>{saving ? "Saving…" : "Save"}</button>
        {onCancel && <button type="button" className="control" onClick={onCancel}>{saved ? "Done" : "Cancel"}</button>}
      </div>
    </fieldset>
    {error && <p role="alert" className="m-0 text-[13px] text-needs-you-ink break-words">{error}</p>}
    {saved && <p role="status" className="m-0 text-[13px] text-done-ink">{saved}</p>}
  </form>;
}
