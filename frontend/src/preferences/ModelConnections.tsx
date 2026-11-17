import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { ConnectionSetup, type SetupResult } from "./ConnectionSetup";
import { Badge } from "./parts";
import { primaryButton, providerOf, secondaryButton, type Connection } from "./providers";
import { listModels } from "./useAction";
import { useWrite, type Entry, type Menu } from "./usePreferences";

/** Guided setup over the same sealed collection used by the settings API. */
export function ModelConnections({ entry, menu }: { entry: Entry; menu?: Menu }) {
  const records = (entry.shown.value as Connection[] | null) ?? [];
  const [editing, setEditing] = useState<Connection | "new" | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [savedName, setSavedName] = useState<string | null>(null);
  const write = useWrite();
  const defaultModel = menu?.sections.flatMap((s) => s.entries).find((e) => e.setting.key === "models.default");
  const fields = entry.setting.fields.map((f) => f.key.split(".").pop()!);
  const serialise = (record: Connection) => Object.fromEntries(fields.map((field) => [field,
    field === "key" ? typeof record.key === "string" ? record.key : null : record[field as keyof Connection] ?? (field === "provider" ? "custom" : ""),
  ]));
  const replace = async (next: Connection[]) => write.mutateAsync({ key: entry.setting.key,
    value: next.filter((r) => !r.locked).map(serialise), served: "mendel" });
  const save = async ({ connection, model, useDefault }: SetupResult) => {
    setSaving(true); setError(null); setSaved(null);
    let connectionSaved = false;
    try {
      await replace([...records.filter((r) => r.name !== connection.name), connection]);
      connectionSaved = true; setSavedName(connection.name);
      if (useDefault && model) await write.mutateAsync({ key: "models.default", served: "mendel",
        value: { connection: connection.name, model, ...(connection.provider === "chatgpt" && { temperature: 1 }) } });
      setEditing(null); setSaved(`${connection.name} saved${useDefault && model ? " and set as the default" : ""}.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Could not save the connection. Try again.";
      setError(connectionSaved ? `Connection saved, but the default model could not be changed. Retry Finish setup. ${message}` : message);
    }
    finally { setSaving(false); }
  };
  const open = (value: Connection | "new") => { setEditing(value); setError(null); setSaved(null); setSavedName(null); };

  return (
    <div className="flex flex-col gap-4">
      {!records.length && !editing && <div className="connection-empty">
        <span className="provider-monogram" aria-hidden>↗</span>
        <div><h3 className="m-0 text-body font-semibold">Choose how Comeni connects</h3>
          <p className="mt-1 mb-0 text-secondary text-ink-3">Local models, API keys, or your ChatGPT subscription.</p></div>
        <button type="button" onClick={() => open("new")} disabled={entry.shown.locked}
          className={primaryButton}>Add connection</button>
      </div>}
      {records.map((record) => <ConnectionCard key={record.name} record={record} disabled={saving || entry.shown.locked}
        onEdit={() => open(record)} onRemove={async () => {
          setError(null); setSaved(null); setSaving(true);
          try { await replace(records.filter((r) => r.name !== record.name)); }
          catch (cause) { setError(cause instanceof Error ? cause.message : "Could not remove this connection."); }
          finally { setSaving(false); }
        }} />)}
      {records.length > 0 && !editing && <button type="button" disabled={entry.shown.locked} onClick={() => open("new")}
        className={`${secondaryButton} self-start`}>Add connection</button>}
      {editing && <ConnectionSetup key={typeof editing === "string" ? "new" : editing.name}
        initial={typeof editing === "string" ? undefined : editing} names={records.map((r) => r.name).filter((n) => n !== savedName)}
        defaultAllowed={!!defaultModel && !defaultModel.shown.locked}
        suggestDefault={!!defaultModel && !defaultModel.shown.locked && !defaultModel.shown.value && editing === "new"}
        pending={saving} error={error} onSave={save} onCancel={() => { setEditing(null); setError(null); }} />}
      {!editing && error && <p role="alert" className="m-0 text-secondary text-needs-you-ink">{error}</p>}
      {saved && <p role="status" className="m-0 text-secondary text-done-ink">{saved}</p>}
    </div>
  );
}

function ConnectionCard({ record, disabled, onEdit, onRemove }: {
  record: Connection; disabled: boolean; onEdit: () => void; onRemove: () => Promise<void>;
}) {
  const provider = providerOf(record);
  const [confirm, setConfirm] = useState(false);
  const check = useMutation({ mutationFn: () => listModels("models.connections", record.name) });
  const key = typeof record.key === "object" ? record.key : null;
  return (
    <div className="connection-record">
      <div className="flex flex-wrap items-center gap-3">
        <span className="provider-monogram" aria-hidden>{provider.mark}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2"><strong className="text-body">{record.name}</strong>
            {record.locked && <Badge>Pinned by .env</Badge>}</div>
          <p className="m-0 text-secondary text-ink-3 break-all">{record.provider && record.provider !== "custom" ? provider.name : record.server === "hosted" ? "Hosted provider" : provider.name}
            {record.endpoint ? ` · ${record.endpoint}` : ""}{key?.set ? ` · key ending ${key.last4 ?? "••••"}` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => check.mutate()} disabled={check.isPending || disabled} className={secondaryButton}>{check.isPending ? "Checking…" : "Check connection"}</button>
          {!record.locked && <><button type="button" onClick={onEdit} disabled={disabled} className={secondaryButton}>Edit</button>
            <button type="button" onClick={() => setConfirm(!confirm)} disabled={disabled} className={secondaryButton}>Remove</button></>}
        </div>
      </div>
      {check.data && <p role="status" className={`mt-3 mb-0 text-secondary ${check.data.ok === false ? "text-needs-you-ink" : "text-ink-2"}`}>{check.data.says}</p>}
      {check.error && <p role="alert" className="mt-3 mb-0 text-secondary text-needs-you-ink">Could not check this connection. Try again.</p>}
      {confirm && <div className="mt-3 flex flex-wrap items-center gap-3 text-secondary text-ink-2">
        <span>Remove {record.name}? Any model choices using it will need another connection.</span>
        <button type="button" disabled={disabled} className={secondaryButton} onClick={async () => {
          try { await onRemove(); } finally { setConfirm(false); }
        }}>{disabled ? "Removing…" : "Remove connection"}</button>
        <button type="button" onClick={() => setConfirm(false)} className={secondaryButton}>Keep connection</button>
      </div>}
    </div>
  );
}
