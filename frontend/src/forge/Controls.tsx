import { useUrlState } from "../app/useUrlState";

/** Sort, group and band — the two controls the design says make one page enough
 *  (`forge-review.md` §4), plus the band filter the facet rail names.
 *
 * Native `<select>`s on purpose: they are keyboard-operable, screen-reader-labelled and
 * correct on a phone without a line of code, and this screen's job is throughput rather
 * than showing off a listbox.
 *
 * **Each one blurs itself after a choice**, and that is not a flourish. `useKeys` ignores
 * any keystroke whose target is an `INPUT`, `TEXTAREA` or `SELECT` — correct, because `J`
 * in a text field is the letter J. But focus stays on a `<select>` after you use it, so
 * without the blur the next `J` is swallowed and the queue's keyboard silently stops
 * working until the user clicks somewhere neutral. They would report it as "the keys
 * sometimes do not work".
 */
const field = "text-body border border-line-2 bg-surface rounded-r px-3 py-1 text-ink";
const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** Set the value, then hand focus back so `J`/`K` keep working. */
const choose = (set: (next: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
  set(e.target.value);
  e.target.blur();
};

export function Controls({ rows, total }: { rows?: number; total?: number }) {
  const [sort, setSort] = useUrlState("sort", "consequence");
  const [group, setGroup] = useUrlState("group", "question");
  const [band, setBand] = useUrlState("band", "");
  const [since, setSince] = useUrlState("since_last_visit", "");

  return (
    <div className="flex items-center gap-5 px-6 py-4 border-b border-line-2">
      <label className="flex items-center gap-2">
        <span className={label}>Sort</span>
        <select className={field} value={sort} onChange={choose(setSort)}>
          <option value="consequence">consequence</option>
          <option value="recent">recent</option>
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className={label}>Group</span>
        <select className={field} value={group} onChange={choose(setGroup)}>
          <option value="question">by question</option>
          <option value="module">by module</option>
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className={label}>Band</span>
        <select className={field} value={band} onChange={choose(setBand)}>
          <option value="">all</option>
          <option value="routing">needs you</option>
          <option value="cosmetic">cosmetic</option>
          <option value="prose">prose</option>
        </select>
      </label>

      <label className="flex items-center gap-2 text-body text-ink-2">
        <input
          type="checkbox"
          checked={since === "true"}
          onChange={(e) => setSince(e.target.checked ? "true" : "")}
        />
        changed since my last visit
      </label>

      {total !== undefined && (
        // Beside the controls rather than elsewhere: these two numbers are what the controls
        // just did. `rows` is what you are looking at, `total` is what is open — and they
        // differ precisely because a filter narrowed or a collapse merged.
        <span className="ml-auto text-secondary text-ink-3">
          <span className="font-data">{rows ?? 0}</span> rows ·{" "}
          <span className="font-data">{total}</span> questions
        </span>
      )}
    </div>
  );
}
