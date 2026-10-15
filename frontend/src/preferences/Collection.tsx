import { useState } from "react";

import { Badge, LockIcon } from "./parts";
import { FIELD } from "./shared";
import { useAction } from "./useAction";
import type { Entry } from "./usePreferences";

/** A list of records — connections today (spec §6), drawn as the overlay's design draws them: one
 * compact card per record, its facts on one quiet line, its actions on the right.
 *
 * **Generic**: the fields come from the declaration and the buttons from its `actions`. A locked
 * record (from .env) is shown and never sent back. A secret field is sent as `null`, which keeps
 * what is stored, unless retyped. Changes wait for *Save connections*, which appears only once
 * there is something to save. */
type Record = { [field: string]: unknown; locked?: boolean };
type Field = {
  key: string; label: string; kind: string; default?: unknown;
  options?: { value: string; label: string }[];
};
type Shape = { key: string; fields: Field[]; item_name: string; actions: string[] };

const nameOf = (field: Field) => field.key.split(".").pop() as string;

/** What an action's button says. The menu's own chrome; an action it does not know is shown by
 *  its name. */
const ACTION_LABEL: { [action: string]: string } = { test: "Test", models: "List models" };
const labelOf = (action: string) =>
  ACTION_LABEL[action] ?? action.charAt(0).toUpperCase() + action.slice(1);

const GHOST = `h-[28px] px-[10px] text-[12px] text-ink-2 bg-transparent border border-line-2 rounded-[3px]
               cursor-pointer hover:text-ink hover:border-ink-4 disabled:opacity-50`;

export function Collection({ entry, onWrite }: { entry: Entry; onWrite: (value: unknown) => void }) {
  const setting = entry.setting as unknown as Shape;
  const records = (entry.shown.value as Record[] | null) ?? [];
  const [added, setAdded] = useState<Record | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [typed, setTyped] = useState<{ [name: string]: { [field: string]: string } }>({});
  const dirty = added !== null || removed.length > 0 || Object.keys(typed).length > 0;

  const kept = records.filter((r) => !r.locked && !removed.includes(String(r[setting.item_name])));
  const plain = (record: Record) =>
    Object.fromEntries(setting.fields.map((f) => {
      const name = nameOf(f);
      const retyped = typed[String(record[setting.item_name])]?.[name];
      if (f.kind === "secret") return [name, retyped ?? null];
      return [name, retyped ?? record[name] ?? ""];
    }));
  /** A new record carries only what was typed or picked, and its key as `null`: a field left
   *  alone takes its declared default on the server (review I1). */
  const fresh = (record: Record) => ({
    ...Object.fromEntries(Object.entries(record).filter(([, v]) => v !== "")),
    ...Object.fromEntries(setting.fields.filter((f) => f.kind === "secret")
      .map((f) => [nameOf(f), (record[nameOf(f)] as string) || null])),
  });
  const save = () => onWrite([...kept.map(plain), ...(added ? [fresh(added)] : [])]);

  return (
    <div className="flex flex-col gap-[8px]">
      <div className="flex justify-end gap-[8px] -mt-[4px] mb-[4px]">
        {dirty && (
          <button type="button" onClick={save}
                  className={`${GHOST} text-ink border-ink-4`}>Save connections</button>
        )}
        <button type="button" onClick={() => setAdded({})} disabled={added !== null}
                className={`${GHOST} inline-flex items-center gap-[6px] text-link border-[var(--link-line)]`}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          Add connection
        </button>
      </div>
      {records.filter((r) => !removed.includes(String(r[setting.item_name]))).map((record) => {
        const name = String(record[setting.item_name]);
        return (
          <Card
            key={name}
            setting={setting}
            record={record}
            onRemove={() => setRemoved([...removed, name])}
            onType={(field, v) => setTyped({ ...typed, [name]: { ...typed[name], [field]: v } })}
          />
        );
      })}
      {added && (
        <div className="border border-line-2 rounded-[3px] bg-[var(--panel)] p-[14px] grid gap-[8px]">
          {setting.fields.map((f) => (
            <label key={f.key} className="grid grid-cols-[90px_minmax(0,1fr)] items-center gap-[12px] text-secondary text-ink-2">
              <span>{nameOf(f)}</span>
              {f.kind === "choice" ? (
                /* A choice is picked from its declared options, never typed (review I1). */
                <select id={`new-${nameOf(f)}`} aria-label={nameOf(f)} defaultValue={String(f.default ?? "")}
                        onChange={(e) => setAdded({ ...added, [nameOf(f)]: e.target.value })}
                        className={FIELD}>
                  {(f.options ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input id={`new-${nameOf(f)}`} aria-label={nameOf(f)}
                       type={f.kind === "secret" ? "password" : "text"}
                       autoComplete="off"
                       onChange={(e) => setAdded({ ...added, [nameOf(f)]: e.target.value })}
                       className={FIELD} />
              )}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

type Status = { ok: boolean | null; says: string } | null;

function Card({ setting, record, onRemove, onType }: {
  setting: Shape; record: Record; onRemove: () => void;
  onType: (field: string, value: string) => void;
}) {
  const name = String(record[setting.item_name]);
  const [status, setStatus] = useState<Status>(null);
  const [editing, setEditing] = useState(false);
  const secrets = setting.fields.filter((f) => f.kind === "secret");
  // The record's facts on one line, in the declaration's order: `ollama · http://… · no key`.
  const facts = setting.fields.filter((f) => nameOf(f) !== setting.item_name).map((f) => {
    const value = record[nameOf(f)];
    if (f.kind === "secret") {
      const mask = value as { set: boolean; last4: string | null } | null;
      if (!mask?.set) return `no ${nameOf(f)}`;
      return mask.last4 ? `${nameOf(f)} ending ${mask.last4}` : `${nameOf(f)} set`;
    }
    return String(value ?? "") || null;
  }).filter(Boolean);

  return (
    <div className="border border-line rounded-[3px] bg-[var(--panel)] px-[14px] py-[12px]">
      <div className="flex flex-wrap items-center gap-x-[16px] gap-y-[8px]">
        <div className="flex flex-col gap-[5px] min-w-0 mr-auto">
          <span className="flex items-center gap-[8px] text-[13.5px] font-medium text-ink">
            {name}
            {record.locked && (
              <Badge tone="text-ink-2 bg-surface border-line-2">
                <LockIcon label="Locked" />Pinned by .env
              </Badge>
            )}
          </span>
          <span className="font-data text-[11px] text-ink-3 break-all">{facts.join(" · ")}</span>
          {status && (
            <span className={`flex items-center gap-[6px] text-secondary
                              ${status.ok === false ? "text-fault" : status.ok ? "text-pea" : "text-ink-2"}`}>
              <span className={`w-[6px] h-[6px] rounded-full shrink-0
                                ${status.ok === false ? "bg-fault" : status.ok ? "bg-pea" : "bg-ink-4"}`} />
              {status.says}
            </span>
          )}
        </div>
        <div className="flex items-center gap-[8px]">
          {setting.actions.map((a) => (
            <Action key={a} setting={setting.key} name={name} action={a} onResult={setStatus} />
          ))}
          {!record.locked && secrets.length > 0 && (
            <button type="button" onClick={() => setEditing(!editing)} aria-expanded={editing}
                    className={GHOST}>Edit</button>
          )}
          {!record.locked && (
            <button type="button" aria-label={`Remove ${name}`} onClick={onRemove}
                    className={`${GHOST} w-[28px] px-0 inline-flex items-center justify-center hover:text-fault`}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="1.8" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
            </button>
          )}
        </div>
      </div>
      {editing && secrets.map((f) => (
        <label key={f.key} className="mt-[12px] grid grid-cols-[90px_minmax(0,1fr)] items-center gap-[12px] text-secondary text-ink-2">
          <span>New {nameOf(f)}</span>
          <input aria-label={`${name} ${nameOf(f)}`} type="password" autoComplete="off"
                 placeholder="kept as it is unless you type one"
                 onChange={(e) => onType(nameOf(f), e.target.value)}
                 className={FIELD} />
        </label>
      ))}
    </div>
  );
}

function Action({ setting, name, action, onResult }: {
  setting: string; name: string; action: string; onResult: (status: Status) => void;
}) {
  const run = useAction(setting, name, action);
  const label = labelOf(action);
  return (
    <button
      type="button"
      disabled={run.isPending}
      onClick={() => run.mutate(undefined, {
        onSuccess: (data) => onResult({ ok: data.ok ?? null, says: data.says }),
        onError: (error) => onResult({ ok: false, says: `Could not run ${label}: ${error.message}` }),
      })}
      className={GHOST}
    >
      {label}
    </button>
  );
}
