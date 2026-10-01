import { useState } from "react";

import { useAction } from "./useAction";
import type { Entry } from "./usePreferences";

/** A list of records — connections today (spec §6). **Generic**: the fields come from the
 * declaration and the buttons from its `actions`. A locked record (from .env) is shown and never
 * sent back. A secret field is sent as `null`, which keeps what is stored, unless retyped. */
type Record = { [field: string]: unknown; locked?: boolean };
type Field = { key: string; label: string; kind: string };

const nameOf = (field: Field) => field.key.split(".").pop() as string;

export function Collection({ entry, onWrite }: { entry: Entry; onWrite: (value: unknown) => void }) {
  const setting = entry.setting as unknown as { key: string; fields: Field[]; item_name: string; actions: string[] };
  const records = (entry.shown.value as Record[] | null) ?? [];
  const [added, setAdded] = useState<Record | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [typed, setTyped] = useState<{ [name: string]: { [field: string]: string } }>({});

  const kept = records.filter((r) => !r.locked && !removed.includes(String(r[setting.item_name])));
  const plain = (record: Record) =>
    Object.fromEntries(setting.fields.map((f) => {
      const name = nameOf(f);
      const retyped = typed[String(record[setting.item_name])]?.[name];
      if (f.kind === "secret") return [name, retyped ?? null];
      return [name, retyped ?? record[name] ?? ""];
    }));
  const save = () => onWrite([...kept.map(plain), ...(added ? [plain(added)] : [])]);

  return (
    <div className="flex flex-col gap-3">
      {records.filter((r) => !removed.includes(String(r[setting.item_name]))).map((record) => (
        <Card key={String(record[setting.item_name])} setting={setting} record={record}
              onRemove={() => setRemoved([...removed, String(record[setting.item_name])])}
              onType={(field, v) => setTyped({ ...typed, [String(record[setting.item_name])]: { ...typed[String(record[setting.item_name])], [field]: v } })} />
      ))}
      {added && (
        <div className="border border-line p-3 flex flex-col gap-2">
          {setting.fields.map((f) => (
            <label key={f.key} className="flex gap-2 items-center text-secondary text-ink-2">
              <span className="w-[90px]">{nameOf(f)}</span>
              <input id={`new-${nameOf(f)}`} aria-label={nameOf(f)}
                     type={f.kind === "secret" ? "password" : "text"}
                     onChange={(e) => setAdded({ ...added, [nameOf(f)]: e.target.value })}
                     className="border border-line bg-transparent px-2 py-1 text-ink w-[260px] max-w-full" />
            </label>
          ))}
        </div>
      )}
      <div className="flex gap-3">
        <button type="button" onClick={() => setAdded({})} disabled={added !== null}
                className="bg-transparent text-link cursor-pointer text-secondary">Add</button>
        <button type="button" onClick={save}
                className="bg-transparent text-link cursor-pointer text-secondary">Save connections</button>
      </div>
    </div>
  );
}

function Card({ setting, record, onRemove, onType }: {
  setting: { key: string; fields: Field[]; item_name: string; actions: string[] };
  record: Record; onRemove: () => void; onType: (field: string, value: string) => void;
}) {
  const name = String(record[setting.item_name]);
  return (
    <div className="border border-line p-3">
      <div className="flex items-baseline gap-2">
        <span className="text-body text-ink">{name}</span>
        {record.locked && <span aria-label="Locked" title="Pinned by .env">🔒</span>}
        <span className="ml-auto flex gap-3">
          {setting.actions.map((a) => <Action key={a} setting={setting.key} name={name} action={a} />)}
          {!record.locked && (
            <button type="button" aria-label={`Remove ${name}`} onClick={onRemove}
                    className="bg-transparent text-ink-3 hover:text-fault cursor-pointer text-secondary">Remove</button>
          )}
        </span>
      </div>
      {setting.fields.filter((f) => nameOf(f) !== setting.item_name).map((f) => {
        const value = record[nameOf(f)];
        if (f.kind === "secret") {
          const mask = value as { set: boolean; last4: string | null } | null;
          return (
            <div key={f.key} className="text-secondary text-ink-2 mt-1">
              {nameOf(f)}: {mask?.set ? `set, ending ${mask.last4}` : "not set"}
              {!record.locked && (
                <input aria-label={`${name} ${nameOf(f)}`} type="password" placeholder="replace"
                       onChange={(e) => onType(nameOf(f), e.target.value)}
                       className="ml-2 border border-line bg-transparent px-2 py-0.5 text-ink w-[180px]" />
              )}
            </div>
          );
        }
        return <div key={f.key} className="text-secondary text-ink-2 mt-1">{nameOf(f)}: {String(value ?? "") || "—"}</div>;
      })}
    </div>
  );
}

function Action({ setting, name, action }: { setting: string; name: string; action: string }) {
  const run = useAction(setting, name, action);
  return (
    <span className="text-secondary">
      <button type="button" onClick={() => run.mutate()} className="bg-transparent text-link cursor-pointer">{action}</button>
      {run.data && <span className={`ml-2 ${run.data.ok === false ? "text-fault" : "text-ink-2"}`}>{run.data.says}</span>}
    </span>
  );
}
