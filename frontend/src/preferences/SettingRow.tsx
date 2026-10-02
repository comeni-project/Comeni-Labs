import { useState } from "react";

import { Refusal } from "../ui/Refusal";
import { Help } from "./Help";
import { Badge, LockIcon } from "./parts";
import { FIELD, sourceOf } from "./shared";
import { useBrowserSetting } from "./useBrowserSetting";
import { Collection } from "./Collection";
import { ModelPicker } from "./ModelPicker";
import { Report } from "./Report";
import type { Entry, Menu } from "./usePreferences";

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
  reported: "Reported",
};

/** `done` is called once the server has accepted the value: a control that must not move on
 *  before then (the secret editor) waits for it (review I-3). */
type Write = (value: unknown, done?: () => void) => void;
type Props = { entry: Entry; onWrite: Write; refusal?: string | null; menu?: Menu };

export function SettingRow(props: Props) {
  return props.entry.setting.where === "browser" ? <InBrowser {...props} /> : <Row {...props} />;
}

function InBrowser({ entry }: Props) {
  const [value, set] = useBrowserSetting(entry.setting.key, String(entry.setting.default));
  return <Row entry={entry} value={value} onWrite={(next) => set(String(next))} badge="This browser" />;
}

/** Kinds drawn on one line beside their label (label · control · source, as the design's model
 *  rows); everything else is drawn under its label. */
const INLINE = new Set(["model", "text", "number", "toggle", "secret"]);

/** The badge for where a value came from. Words are the menu's own chrome; colour says one thing:
 *  blue is *you set this here*, everything else is quiet. */
const TONE: Record<string, string> = {
  installation: "text-link bg-link-soft border-[var(--link-line)]",
  environment: "text-ink-2 bg-surface border-line-2",
};

/** The first sentence of the help, shown under an inline row's label; the ⓘ holds the rest. */
const hintOf = (help: string) => help.split(/(?<=\.)\s+/)[0];

function Row({
  entry, onWrite, refusal, menu, value = entry.shown.value, badge,
}: Props & { value?: unknown; badge?: string }) {
  const { setting, shown } = entry;
  const reason = shown.reason ?? null;
  const designed = reason?.kind === "designed";
  const inline = INLINE.has(setting.kind) || (setting.kind === "readonly" && !Array.isArray(value));
  const from = sourceOf(entry);
  const source = (
    <Badge tone={badge ? "" : TONE[from] ?? ""}>
      {from === "environment" && !badge && <LockIcon />}
      {badge ?? SOURCE[from]}
    </Badge>
  );
  const control = (
    <Control entry={entry} value={value} disabled={shown.locked} onWrite={onWrite} menu={menu} />
  );
  return (
    <div data-testid="preference" className="py-[14px] border-t border-line-soft first:border-t-0">
      <div
        className={`grid gap-x-[20px] gap-y-[8px] items-center grid-cols-[minmax(0,1fr)_auto]
                    ${inline ? "md:grid-cols-[minmax(0,1fr)_280px_110px]" : ""}`}
      >
        <div className="relative flex flex-wrap items-center gap-x-[6px] gap-y-[4px] min-w-0">
          <label
            htmlFor={setting.key}
            className={`text-body ${shown.locked ? "text-ink-2" : "text-ink"}`}
          >
            {setting.label}
          </label>
          <Help label={setting.label} help={setting.help} reason={reason?.says} locked={shown.locked} />
          {shown.locked && !designed && (
            <span className="text-ink-3 inline-flex"><LockIcon label="Locked" /></span>
          )}
          {designed && <Badge dashed>Not built</Badge>}
          {inline && (
            <span className="basis-full text-secondary text-ink-4">{hintOf(setting.help)}</span>
          )}
        </div>
        {inline ? (
          <>
            <div className="col-span-2 md:col-span-1 order-last md:order-none min-w-0">{control}</div>
            <div className="justify-self-end">{source}</div>
          </>
        ) : (
          <>
            <div className="justify-self-end">{source}</div>
            <div className="col-span-2 min-w-0">{control}</div>
          </>
        )}
      </div>
      {refusal && <div className="mt-[8px]"><Refusal message={refusal} /></div>}
    </div>
  );
}

function Control({
  entry, value, disabled, onWrite, menu,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: Write; menu?: Menu }) {
  const { setting, shown } = entry;
  switch (setting.kind) {
    case "choice":
      // **A segmented control** (the design's Building rows). The radio sits inside each
      // segment's label, so a keyboard and a screen reader meet a plain radio group; a greyed
      // setting is drawn dashed rather than only faded. **An option that is designed and not
      // built** is drawn the same way, alone, with why under the group: the menu says what is
      // coming without offering a choice nothing would honour.
      const designed = (setting.options ?? []).filter((option) => option.designed);
      return (
        <div className="flex flex-col gap-[4px] max-w-full">
        <div
          role="radiogroup"
          aria-label={setting.label}
          // Stacked rows on a phone, one segmented line on a desk (the design's phone artboard).
          className={`flex flex-col md:inline-flex md:flex-row md:flex-wrap max-w-full
                      rounded-[3px] border border-line-2 ${disabled ? "border-dashed" : ""}`}
        >
          {(setting.options ?? []).map((option) => {
            const on = value === option.value;
            const off = disabled || Boolean(option.designed);
            return (
              <label
                key={option.value}
                className={`px-[12px] py-[8px] min-h-[44px] md:min-h-0 flex items-center
                            text-[12px] border-b last:border-b-0 md:border-b-0 md:border-r
                            md:last:border-r-0 border-line-2
                            ${off ? "border-dashed cursor-not-allowed" : "cursor-pointer"}
                            ${on ? "bg-hover text-ink" : option.designed ? "text-ink-4" : "text-ink-3"}
                            ${!off && !on ? "hover:text-ink" : ""}
                            has-[:focus-visible]:shadow-[var(--ring)]`}
              >
                <input
                  type="radio"
                  className="sr-only"
                  name={setting.key}
                  value={option.value}
                  checked={on}
                  disabled={off}
                  onChange={() => onWrite(option.value)}
                />
                {option.label}
              </label>
            );
          })}
        </div>
        {designed.map((option) => (
          <p key={option.value} className="text-[11px] text-ink-4">
            {option.label}: {option.designed}
          </p>
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
      // **Keyed by the server's value** (review I-2): a refused or normalised save reloads the
      // menu, and the field shows what the server holds rather than the draft it refused.
      return <Typed key={String(value)} entry={entry} value={value} disabled={disabled} onWrite={onWrite} numeric />;
    case "text":
      return <Typed key={String(value)} entry={entry} value={value} disabled={disabled} onWrite={onWrite} />;
    case "secret":
      return <Secret entry={entry} disabled={disabled} onWrite={onWrite} set={shown.set === true} last4={shown.last4 ?? null} />;
    case "collection":
      return <Collection entry={entry} onWrite={onWrite} />;
    case "model":
      return menu ? <ModelPicker entry={entry} menu={menu} onWrite={onWrite} /> : null;
    case "readonly":
      return <Report value={value} />;
    default:
      return <span className="font-data text-secondary text-ink-2">{value === null ? "—" : String(value)}</span>;
  }
}

function Typed({
  entry, value, disabled, onWrite, numeric = false,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: Write; numeric?: boolean }) {
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
      className={FIELD}
    />
  );
}

function Secret({
  entry, disabled, onWrite, set, last4,
}: { entry: Entry; disabled: boolean; onWrite: Write; set: boolean; last4: string | null }) {
  // **Derived from the server's `set`** (review I-3): a secret the server stops showing as set
  // opens the editor again, and the editor closes only once a save has been accepted.
  const [replacing, setReplacing] = useState(false);
  const [draft, setDraft] = useState("");
  if (set && !replacing) {
    return (
      <span className="flex items-center gap-[12px] text-secondary text-ink-2">
        {last4 ? `Set, ending ${last4}` : "Set"}
        <button type="button" disabled={disabled} onClick={() => setReplacing(true)}
                className="bg-transparent text-link cursor-pointer">Replace</button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-[8px]">
      <input
        id={entry.setting.key}
        type="password"
        autoComplete="off"
        aria-label={entry.setting.label}
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        className={FIELD}
      />
      <button type="button" disabled={disabled || !draft}
              onClick={() => onWrite(draft, () => { setDraft(""); setReplacing(false); })}
              className="bg-transparent text-link cursor-pointer">Save</button>
    </span>
  );
}
