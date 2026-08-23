import type { components } from "../api/schema";
import { useTiers } from "./useTiers";

type Step = components["schemas"]["StepView"];
type Setting = components["schemas"]["SettingView"];

/** Grouped by **how each was decided, ordered by what needs attention** — `dashboard.md` §5.
 *
 * The two that need a person open by default and the two that do not are collapsed. That is the
 * point of the card rather than a nicety: most settings need no attention, and the card says so
 * without hiding them.
 */
/** Which groups open by default — `dashboard.md` §5. **The two that need a person.**
 *
 * The *order* and the *open* flag are a design decision and stay here; the **names** come from
 * the API, because they are a vocabulary and this was one of two places retyping it. */
const OPEN_BY_DEFAULT = new Set([4, 3]);
const GROUP_ORDER = [4, 3, 2, 1];

const EDGE: Record<number, string> = {
  1: "border-l-pea",
  2: "border-l-pea/40",
  3: "border-l-[var(--measured)]",
  4: "border-l-[var(--undecided)]",
};

/** The control a setting's declared domain asks for.
 *
 * `dashboard.md` §5: *parameters with alternatives render as a `<select>`; free values as an
 * input*. The domain comes from the contract — `enum` lists its values, `boolean` is two, and a
 * param that declares none gets a text box because its legal values genuinely cannot be
 * enumerated. `seq_platform` is the deliberate example: the list of sequencing platforms is open.
 */
function Field({
  setting,
  onSet,
}: {
  setting: Setting;
  onSet: (value: string | null) => void;
}) {
  const kind = setting.domain?.kind;
  const shared =
    "ml-auto font-data text-body rounded-r border px-2 py-0.5 bg-bg text-ink " +
    (setting.tier === 4 ? "border-[var(--undecided)]" : "border-line");

  if (kind === "enum" || kind === "boolean") {
    const options = kind === "boolean" ? ["true", "false"] : setting.domain!.values;
    return (
      <select
        data-testid="setting-field"
        className={shared}
        value={setting.value ?? ""}
        onChange={(e) => onSet(e.target.value === "" ? null : e.target.value)}
      >
        {/* An undecided setting has no value, and the blank option is how you can see that
            rather than being shown someone else's first alternative as if it were an answer. */}
        <option value="">—</option>
        {options.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      data-testid="setting-field"
      className={shared + " w-40"}
      type={kind === "integer" || kind === "number" ? "number" : "text"}
      min={setting.domain?.minimum ?? undefined}
      max={setting.domain?.maximum ?? undefined}
      value={setting.value ?? ""}
      placeholder="—"
      onChange={(e) => onSet(e.target.value === "" ? null : e.target.value)}
    />
  );
}

function Row({
  setting,
  onSet,
}: {
  setting: Setting;
  onSet?: (name: string, value: string | null) => void;
}) {
  return (
    <div
      data-testid="setting"
      data-tier={setting.tier}
      className={`border-l-2 pl-3 py-2 ${EDGE[setting.tier] ?? "border-l-line"}`}
    >
      <div className="flex items-baseline gap-3">
        <span className="font-data text-body text-ink">{setting.name}</span>
        {onSet ? (
          <Field setting={setting} onSet={(v) => onSet(setting.name, v)} />
        ) : (
          <span
            className="ml-auto font-data text-body text-ink-2
                       data-[none]:text-ink-3"
            data-none={setting.value === null || undefined}
          >
            {/* **An absence, not an empty box.** A tier-4 setting has no value because nobody
                has decided one; rendering `""` would read as *decided, to nothing*. */}
            {setting.value ?? "—"}
          </span>
        )}
      </div>
      {setting.axis_reason && (
        <div className="text-secondary text-ink-3 mt-1">{setting.axis_reason}</div>
      )}
      <div className="text-secondary text-ink-2 mt-1">{setting.reason}</div>
      {/* **The convention you departed from, kept visible.** `reason` becomes *your* reason
          the moment you type a value; `because` is the contract author's note on the default
          and survives the override, so the thing you overrode is still readable. */}
      {setting.because && setting.because !== setting.reason && (
        <div data-testid="setting-because" className="text-secondary text-ink-3 mt-1 italic">
          {setting.because}
        </div>
      )}
      <div className="text-label text-ink-3 mt-1 font-data">via {setting.via}</div>
    </div>
  );
}

/** Every parameter of one step, and how each was settled.
 *
 * **Read-only, and the field is absent rather than disabled.** The design has an editable input
 * per row; nothing in 3C persists an answer, and a box that looks typeable and discards what you
 * type is worse than a value that admits it is a record. It becomes editable when there is
 * somewhere to put the answer — which is the same reason a dragged node does not stay dragged.
 */
export function Settings({
  step,
  onClose,
  onSet,
}: {
  step: Step;
  onClose: () => void;
  /** Set a parameter on this step. Omitted where the card is a record rather than a control. */
  onSet?: (name: string, value: string | null) => void;
}) {
  const words = useTiers();
  const groups = GROUP_ORDER.map((tier) => ({
    tier,
    name: words.group(tier),
    open: OPEN_BY_DEFAULT.has(tier),
    rows: step.settings.filter((setting) => setting.tier === tier),
  })).filter((group) => group.rows.length > 0);

  return (
    <div data-testid="settings-card" className="p-4">
      <div className="flex items-baseline gap-3 mb-3">
        <span className="font-data text-body font-semibold text-ink">{step.process}</span>
        <button
          onClick={onClose}
          className="ml-auto text-secondary text-ink-3 bg-transparent border-0 cursor-pointer p-0"
        >
          close
        </button>
      </div>

      {groups.length === 0 && (
        <p className="text-body text-ink-2 m-0">
          This step takes no parameters. Everything it does is forced by the module.
        </p>
      )}

      {groups.map((group) => (
        <details key={group.tier} open={group.open} className="mb-3">
          <summary className="cursor-pointer text-label uppercase tracking-[.13em] font-semibold text-ink-3">
            {group.name} <span className="font-data text-ink-2">{group.rows.length}</span>
          </summary>
          <div className="mt-2 flex flex-col gap-1">
            {group.rows.map((setting) => (
              <Row key={setting.name} setting={setting} onSet={onSet} />
            ))}
          </div>
        </details>
      ))}

      <p className="text-label text-ink-3 mt-4 mb-0">
        {/* Said on the screen, not only in a docstring. */}
        {onSet
          ? "A value you set exits at tier 4 and is recorded as yours — see the review rail."
          : "Read-only: this pipeline is a record rather than a draft."}
      </p>
    </div>
  );
}
