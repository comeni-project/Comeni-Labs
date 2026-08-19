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

function Row({ setting }: { setting: Setting }) {
  return (
    <div
      data-testid="setting"
      data-tier={setting.tier}
      className={`border-l-2 pl-3 py-2 ${EDGE[setting.tier] ?? "border-l-line"}`}
    >
      <div className="flex items-baseline gap-3">
        <span className="font-data text-body text-ink">{setting.name}</span>
        <span
          className="ml-auto font-data text-body text-ink-2
                     data-[none]:text-ink-3"
          data-none={setting.value === null || undefined}
        >
          {/* **An absence, not an empty box.** A tier-4 setting has no value because nobody has
              decided one; rendering `""` would read as *decided, to nothing*. */}
          {setting.value ?? "—"}
        </span>
      </div>
      {setting.axis_reason && (
        <div className="text-secondary text-ink-3 mt-1">{setting.axis_reason}</div>
      )}
      <div className="text-secondary text-ink-2 mt-1">{setting.reason}</div>
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
export function Settings({ step, onClose }: { step: Step; onClose: () => void }) {
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
              <Row key={setting.name} setting={setting} />
            ))}
          </div>
        </details>
      ))}

      <p className="text-label text-ink-3 mt-4 mb-0">
        {/* Said on the screen, not only in a docstring. */}
        Read-only until a pipeline has somewhere to be saved.
      </p>
    </div>
  );
}
