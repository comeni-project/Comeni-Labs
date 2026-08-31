import { useState } from "react";

import type { AnsweredStep, Answered as Setting } from "./useBuilder";
import { open as isOpen } from "./useBuilder";
import { useTiers } from "./useTiers";

/** **Three bands, ordered by what could need you** — `n-bsettings` and `impl-settled`.
 *
 * > THE SETTINGS CARD IS ORDERED BY WHAT COULD NEED YOU: no-rule values first as CHOICES not a
 * > text field, then measured with its premise, then 'n settled' folded. Never alphabetical.
 *
 * It shipped as four `<details>` groups, one per tier, two open and two closed — which is the
 * same information and a different claim. Four equal groups say *here are your parameters, by
 * category*; three bands say *two of these need you, one was measured, and the rest are
 * finished*. The card exists to answer the second question, and the artboard draws it that way:
 * a tinted red band, an amber one, and a single folded line.
 *
 * **The last band is two tiers folded into one row**, and that is the only place this file
 * writes a word the API does not own. `useTiers` serves a `group` per tier because a tier is
 * load-bearing vocabulary; *settled* is not a tier, it is the canvas's word for the collapse of
 * tiers 1 and 2, and `Node.tsx`'s footer already says it. One word, one meaning, two places.
 *
 * **Folded is not read-only.** Everything in the third band stays answerable once it is open,
 * because departing from a convention is a thing a person is allowed to do — it is what
 * `because` exists to keep visible, and a band that only displayed would make that field
 * describe something nobody could reach.
 */
const NEEDS_YOU = 4;
const MEASURED = 3;

/** What a person may answer with.
 *
 * `impl-settled` asks for **choices, not a text field** — and that is only possible where the
 * contract enumerates the alternatives. `seq_platform` declares no domain on purpose: the list
 * of sequencing platforms is open, so there is nothing to draw chips from and an input is the
 * honest control. Rendering three invented chips there would be a closed vocabulary the registry
 * never declared.
 */
function choices(setting: Setting): string[] | null {
  const kind = setting.domain?.kind;
  if (kind === "boolean") return ["true", "false"];
  if (kind === "enum" && setting.domain!.values.length > 0) return setting.domain!.values;
  return null;
}

/** A chip's label, typed the way the contract's domain declares it.
 *
 * **`SettingView.value` is a string and `DraftParam.value` is not.** The resolver renders every
 * value for display — a boolean arrives as Python's `"False"` — and `Domain.refuse` accepts a
 * boolean domain only when the value *is* a bool. The `<select>` this replaced sent the string
 * `"false"` for a boolean parameter, which is a shape the contract would refuse; a chip is one
 * click from doing the same, so the coercion lives here rather than being someone's later
 * surprise.
 */
function typed(setting: Setting, label: string): string | number | boolean {
  const kind = setting.domain?.kind;
  if (kind === "boolean") return label === "true";
  if (kind === "integer" || kind === "number") return Number(label);
  return label;
}

/** Whether a chip is the value this setting currently holds.
 *
 * **Case-insensitive, and that is not sloppiness.** A boolean comes back for display as `False`
 * and the domain's own words are `true` / `false`, so an exact comparison marks nothing — a
 * settled boolean read as unanswered in every card. Enum values are compared the same way
 * because two enum members differing only in case would be a registry defect, not a case this
 * has to preserve.
 */
function chosen(setting: Setting, label: string): boolean {
  return setting.value !== null && setting.value.toLowerCase() === label.toLowerCase();
}

const CHIP =
  "font-data text-label px-[9px] py-[5px] border cursor-pointer lift bg-transparent";

/** One parameter: what it is, what it is set to, how to change it, and why it says that.
 *
 * The same row in all three bands. What differs between them is the **heading, the tint and the
 * order** — not the anatomy of a value, which would be three ways of drawing one thing.
 */
function Row({
  setting,
  onSet,
}: {
  setting: Setting;
  onSet?: (value: string | number | boolean | null) => void;
}) {
  const options = choices(setting);
  const open = setting.tier === NEEDS_YOU;
  // **Where there is a control, the control IS the value.** A field shows what the setting is
  // set to and a chip row marks the one that is chosen, so a right-aligned copy beside either
  // is the same string twice — `bai   [bai] [csi]`, and when the value is null it is an em-dash
  // beside a placeholder em-dash, which reads as two different absences.
  const echo = !onSet;

  return (
    <div data-testid="setting" data-tier={setting.tier} className="pb-[13px] last:pb-1">
      <div className="flex items-baseline justify-between gap-3 pb-[7px]">
        <span className="font-data text-secondary text-ink">{setting.name}</span>
        {/* **An absence, not an empty box.** A tier-4 setting has no value because nobody
            decided one; rendering `""` would read as *decided, to nothing*. */}
        {echo && (
          <span
            data-testid="setting-value"
            className={`font-data text-secondary ${
              setting.value === null ? "text-ink-3" : "text-ink"
            }`}
          >
            {setting.value ?? "—"}
          </span>
        )}
      </div>

      {onSet &&
        (options ? (
          <div data-testid="setting-choices" className="flex gap-[5px] flex-wrap">
            {options.map((value) => {
              const on = chosen(setting, value);
              return (
                <button
                  key={value}
                  type="button"
                  data-testid="setting-choice"
                  data-on={on || undefined}
                  // **Clicking the chosen chip clears it.** A tier-4 answer is a person's, and
                  // taking it back has to be possible without a blank entry in a list of legal
                  // values — which is what the `<select>`'s empty option used to be.
                  onClick={() => onSet(on ? null : typed(setting, value))}
                  className={
                    CHIP +
                    (on
                      ? " border-link bg-[var(--link-soft)] text-link"
                      : " border-line-2 text-ink-2 hover:text-ink")
                  }
                >
                  {value}
                </button>
              );
            })}
          </div>
        ) : (
          <input
            data-testid="setting-field"
            className={
              "font-data text-body rounded-r border px-2 py-0.5 bg-bg text-ink w-full " +
              (open ? "border-[var(--undecided)]" : "border-line")
            }
            type={
              setting.domain?.kind === "integer" || setting.domain?.kind === "number"
                ? "number"
                : "text"
            }
            min={setting.domain?.minimum ?? undefined}
            max={setting.domain?.maximum ?? undefined}
            value={setting.value ?? ""}
            placeholder="—"
            onChange={(e) =>
              onSet(e.target.value === "" ? null : typed(setting, e.target.value))
            }
          />
        ))}

      {/* `axis_reason` answers *why this axis* and `reason` answers *why this answer* — Plan
          1.14 split them because one string was doing both, which is how the registry came to
          cite the STAR paper as the reason HISAT2 was chosen. */}
      {/* **Whose answer this is, said on the row.** A tier-4 value that a person chose keeps
          its tier and its band; what separates it from one nobody has touched is this word, and
          without it the two are drawn identically. */}
      {setting.answered && (
        <div data-testid="setting-yours" className="text-label font-data text-link pt-[7px]">
          yours
        </div>
      )}
      {setting.axis_reason && (
        <div className="text-secondary text-ink-3 pt-[7px] leading-[1.45]">
          {setting.axis_reason}
        </div>
      )}
      <div className="text-secondary text-ink-3 pt-[7px] leading-[1.45]">{setting.reason}</div>
      {/* **The convention you departed from, kept visible.** `reason` becomes *your* reason the
          moment you answer; `because` is the contract author's note on the default and survives
          the override, so the thing you overrode is still readable. */}
      {setting.because && setting.because !== setting.reason && (
        <div data-testid="setting-because" className="text-secondary text-ink-3 pt-[5px] italic">
          {setting.because}
        </div>
      )}
      <div className="text-label text-ink-4 pt-[5px] font-data">via {setting.via}</div>
    </div>
  );
}

const BAND = "text-label font-data uppercase tracking-[.15em]";

/** Every parameter of one step, and how each was settled.
 *
 * **The card owns the VALUES and the rail owns the CHOICE** — `impl-settled`. Two lists of the
 * same thing is what the redesign removed, so this is the only place a parameter is rendered.
 */
export function Settings({
  step,
  onClose,
  onSet,
}: {
  step: AnsweredStep;
  onClose: () => void;
  /** Answer a parameter on this step. Omitted where the card is a record rather than a control. */
  onSet?: (name: string, value: string | number | boolean | null) => void;
}) {
  const words = useTiers();
  const [showing, setShowing] = useState(false);

  // **The first band holds every tier-4 value, and its HEADING counts only what is still
  // open.** A value you answered keeps its tier for good (invariant 6) — but *needs your
  // decision* is false about one you already decided, so the heading and the tint follow the
  // worst row rather than the tier.
  //
  // **Moving an answered value to a band of its own was tried and is wrong**, and the way it
  // failed is the useful part: typing one character marks the value answered, the row moves,
  // React unmounts the input — and `ILLUMINA` typed into the box left `I` behind. A control
  // must not migrate out from under the cursor that is using it. Same defect the
  // `withTypedValues` docstring already records from the other direction.
  const flagged = step.settings.filter((one) => one.tier === NEEDS_YOU);
  const still = flagged.filter(isOpen).length;
  const measured = step.settings.filter((one) => one.tier === MEASURED);
  const settled = step.settings.filter((one) => one.tier < MEASURED);

  const set = (setting: Setting) =>
    onSet && ((value: string | number | boolean | null) => onSet(setting.name, value));

  return (
    <div data-testid="settings-card">
      <div
        className="flex items-baseline justify-between gap-3 px-[15px] py-3 border-b
                   border-line"
      >
        <span className="font-data text-body font-medium text-ink">{step.process}</span>
        <div className="flex items-baseline gap-4">
          <span className="font-data text-label text-ink-4">
            {step.settings.length} {step.settings.length === 1 ? "setting" : "settings"}
          </span>
          <button
            onClick={onClose}
            className="text-secondary text-ink-3 bg-transparent border-0 cursor-pointer p-0
                       hover:text-ink"
          >
            close
          </button>
        </div>
      </div>

      {step.settings.length === 0 && (
        <p className="px-[15px] py-4 text-body text-ink-2 m-0">
          This step takes no parameters. Everything it does is forced by the module.
        </p>
      )}

      {flagged.length > 0 && (
        <div
          data-testid="band-needs-you"
          data-open={still || undefined}
          className={
            "settle px-[15px] pt-3 pb-1 border-b border-line " +
            (still > 0 ? "bg-[color-mix(in_srgb,var(--undecided)_5%,transparent)]" : "")
          }
        >
          {/* Invariant 6: tier 4 is always flagged, and this is one of its four places. The
              heading changes when nothing here is open any more; the band does not go away. */}
          <div
            className={`${BAND} pb-[11px] ${still > 0 ? "text-[var(--undecided)]" : "text-link"}`}
          >
            {still > 0
              ? `${words.group(NEEDS_YOU)} · ${still}`
              : `Answered by you · ${flagged.length}`}
          </div>
          {flagged.map((setting) => (
            <Row key={setting.name} setting={setting} onSet={set(setting)} />
          ))}
        </div>
      )}

      {measured.length > 0 && (
        <div
          data-testid="band-measured"
          className="settle px-[15px] pt-3 pb-1 border-b border-line"
          style={{ animationDelay: "40ms" }}
        >
          <div className={`${BAND} text-[var(--measured)] pb-[10px]`}>
            {words.group(MEASURED)} · {measured.length}
          </div>
          {measured.map((setting) => (
            <Row key={setting.name} setting={setting} onSet={set(setting)} />
          ))}
        </div>
      )}

      {settled.length > 0 && (
        <div className="settle" style={{ animationDelay: "80ms" }}>
          <button
            type="button"
            data-testid="show-settled"
            aria-expanded={showing}
            onClick={() => setShowing((was) => !was)}
            className="w-full flex items-center justify-between px-[15px] py-[11px]
                       bg-transparent border-0 cursor-pointer lift text-left"
          >
            <span className="text-body text-ink-2">{settled.length} settled</span>
            <span className="font-data text-label text-link">
              {showing ? "hide ▴" : "show ▾"}
            </span>
          </button>
          {showing && (
            <div data-testid="band-settled" className="px-[15px] pb-1 border-t border-line pt-3">
              {settled.map((setting) => (
                <Row key={setting.name} setting={setting} onSet={set(setting)} />
              ))}
            </div>
          )}
        </div>
      )}

      <p className="text-label text-ink-4 px-[15px] py-3 m-0 border-t border-line">
        {/* Said on the screen, not only in a docstring. */}
        {onSet
          ? "A value you answer exits at tier 4 and is recorded as yours."
          : "Read-only: this pipeline is a record rather than a draft."}
      </p>
    </div>
  );
}
