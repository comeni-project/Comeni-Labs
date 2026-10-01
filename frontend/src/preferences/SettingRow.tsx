import { useState } from "react";

import { Refusal } from "../ui/Refusal";
import { Help } from "./Help";
import { useBrowserSetting } from "./useBrowserSetting";
import type { Entry } from "./usePreferences";

/** One setting, any kind (spec §4, §5).
 *
 * **Knows no particular setting.** It reads `kind` and draws the control for it; a kind it has
 * never heard of is drawn as read-only text, so a newer API never breaks an older page. The only
 * words it writes itself are the source badges and its buttons.
 */
const SOURCE: Record<string, string> = {
  default: "Default",
  installation: "Set here",
  environment: "Pinned by .env",
};

type Props = { entry: Entry; onWrite: (value: unknown) => void; refusal?: string | null };

export function SettingRow(props: Props) {
  return props.entry.setting.where === "browser" ? <InBrowser {...props} /> : <Row {...props} />;
}

function InBrowser({ entry }: Props) {
  const [value, set] = useBrowserSetting(entry.setting.key, String(entry.setting.default));
  return <Row entry={entry} value={value} onWrite={(next) => set(String(next))} badge="This browser" />;
}

function Row({
  entry, onWrite, refusal, value = entry.shown.value, badge,
}: Props & { value?: unknown; badge?: string }) {
  const { setting, shown } = entry;
  const reason = shown.reason ?? null;
  const designed = reason?.kind === "designed";
  return (
    <div data-testid="preference" className="py-3 border-b border-line-soft last:border-b-0">
      <div className="flex items-baseline gap-2">
        <label htmlFor={setting.key} className="text-body text-ink">{setting.label}</label>
        <Help label={setting.label} help={setting.help} reason={reason?.says} />
        {shown.locked && !designed && <span aria-label="Locked" title="Locked">🔒</span>}
        {designed && (
          <span className="text-secondary text-ink-3 border border-line px-1">not built</span>
        )}
        <span className="ml-auto text-secondary text-ink-3">{badge ?? SOURCE[shown.source]}</span>
      </div>
      <div className="mt-2">
        <Control entry={entry} value={value} disabled={shown.locked} onWrite={onWrite} />
      </div>
      {refusal && <div className="mt-2"><Refusal message={refusal} /></div>}
    </div>
  );
}

function Control({
  entry, value, disabled, onWrite,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: (value: unknown) => void }) {
  const { setting, shown } = entry;
  switch (setting.kind) {
    case "choice":
      return (
        <div role="radiogroup" aria-label={setting.label} className="flex flex-wrap gap-4">
          {(setting.options ?? []).map((option) => (
            <label key={option.value} className="flex items-center gap-1 text-secondary text-ink">
              <input
                type="radio"
                name={setting.key}
                value={option.value}
                checked={value === option.value}
                disabled={disabled}
                onChange={() => onWrite(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      );
    case "toggle":
      return (
        <input
          id={setting.key}
          type="checkbox"
          aria-label={setting.label}
          checked={value === true}
          disabled={disabled}
          onChange={(event) => onWrite(event.target.checked)}
        />
      );
    case "number":
      return <Typed entry={entry} value={value} disabled={disabled} onWrite={onWrite} numeric />;
    case "text":
      return <Typed entry={entry} value={value} disabled={disabled} onWrite={onWrite} />;
    case "secret":
      return <Secret entry={entry} disabled={disabled} onWrite={onWrite} set={shown.set === true} last4={shown.last4 ?? null} />;
    default:
      return <span className="font-data text-secondary text-ink-2">{value === null ? "—" : String(value)}</span>;
  }
}

function Typed({
  entry, value, disabled, onWrite, numeric = false,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: (v: unknown) => void; numeric?: boolean }) {
  const [draft, setDraft] = useState(value === null ? "" : String(value));
  const commit = () => {
    if (draft === String(value ?? "")) return;
    onWrite(numeric ? Number(draft) : draft);
  };
  return (
    <input
      id={entry.setting.key}
      type={numeric ? "number" : "text"}
      aria-label={entry.setting.label}
      value={draft}
      disabled={disabled}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => event.key === "Enter" && commit()}
      className="border border-line bg-transparent px-2 py-1 text-secondary text-ink w-[260px] max-w-full"
    />
  );
}

function Secret({
  entry, disabled, onWrite, set, last4,
}: { entry: Entry; disabled: boolean; onWrite: (v: unknown) => void; set: boolean; last4: string | null }) {
  const [editing, setEditing] = useState(!set);
  const [draft, setDraft] = useState("");
  if (!editing) {
    return (
      <span className="flex items-center gap-3 text-secondary text-ink-2">
        Set, ending {last4}
        <button type="button" disabled={disabled} onClick={() => setEditing(true)}
                className="bg-transparent text-link cursor-pointer">Replace</button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <input
        id={entry.setting.key}
        type="password"
        autoComplete="off"
        aria-label={entry.setting.label}
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        className="border border-line bg-transparent px-2 py-1 text-secondary text-ink w-[260px] max-w-full"
      />
      <button type="button" disabled={disabled || !draft}
              onClick={() => { onWrite(draft); setDraft(""); setEditing(false); }}
              className="bg-transparent text-link cursor-pointer">Save</button>
    </span>
  );
}
