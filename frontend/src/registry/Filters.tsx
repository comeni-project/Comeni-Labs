import type { CataloguePage } from "./useCatalogue";
import { useFilters } from "./useCatalogue";
import { PLACEHOLDER_NOTE, STATES } from "./states";

const SHOWN_TOPICS = 7;
const SHOWN_FORMATS = ["fastq", "fasta", "bam", "vcf", "bed", "tif", "mzml"];

const count = "ml-auto font-data text-[12px] text-ink-3 tabular-nums";
const legend = "text-[12px] font-semibold text-ink-2 mb-2 p-0";

/** The left column of board 1: state, topic, reads-or-makes and source. Counts are over the
 *  whole catalogue, so each says how many a filter would show. */
export function Filters({ counts }: { counts: CataloguePage["counts"] }) {
  const filters = useFilters();
  const topics = Object.entries(counts.topics).sort((a, b) => b[1] - a[1]).slice(0, SHOWN_TOPICS);
  const formats = SHOWN_FORMATS.filter((f) => f in counts.formats);
  const toggle = (key: "topic" | "format", list: string[], value: string) =>
    filters.set(key, list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const total = Object.values(counts.states).reduce((a, b) => a + b, 0);

  return (
    <aside aria-label="Filters" className="flex flex-col gap-[26px]">
      <fieldset className="border-0 m-0 p-0 flex flex-col gap-[2px]">
        <legend className={legend}>In the registry</legend>
        <StateOption label="All modules" value="" n={total} />
        {STATES.map(({ state, label, placeholder }) => (
          <StateOption key={state} label={label} value={state} n={counts.states[state] ?? 0}
                       note={placeholder ? PLACEHOLDER_NOTE : undefined} />
        ))}
      </fieldset>

      {topics.length > 0 && (
        <fieldset className="border-0 m-0 p-0 flex flex-col gap-[2px]">
          <legend className={legend}>Topic</legend>
          {topics.map(([topic, n]) => (
            <label key={topic} className="flex items-center gap-[9px] px-2 py-[6px] cursor-pointer capitalize">
              <input type="checkbox" className="accent-action" checked={filters.topics.includes(topic)}
                     onChange={() => toggle("topic", filters.topics, topic)} />
              {topic}<span className={count}>{n}</span>
            </label>
          ))}
        </fieldset>
      )}

      {formats.length > 0 && (
        <fieldset className="border-0 m-0 p-0">
          <legend className={legend}>Reads or makes</legend>
          <div className="flex flex-wrap gap-[6px]">
            {formats.map((format) => (
              <label key={format}
                     className="inline-flex items-center gap-[6px] px-[10px] py-[5px] border border-line-2 rounded-full font-data text-[12px] bg-surface cursor-pointer">
                <input type="checkbox" className="accent-action m-0" checked={filters.formats.includes(format)}
                       onChange={() => toggle("format", filters.formats, format)} />
                {format}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset className="border-0 m-0 p-0 flex flex-col gap-[2px]">
        <legend className={legend}>Source</legend>
        <label className="flex items-center gap-[9px] px-2 py-[6px]">
          <input type="checkbox" checked readOnly className="accent-action" />nf-core
          <span className={count}>{counts.sources["nf-core"] ?? 0}</span>
        </label>
        <label className="flex items-center gap-[9px] px-2 py-[6px] text-ink-3">
          <input type="checkbox" disabled />pegi3s<span className="ml-auto text-[12px]">later</span>
        </label>
      </fieldset>
    </aside>
  );
}

function StateOption({ label, value, n, note }: { label: string; value: string; n: number; note?: string }) {
  const filters = useFilters();
  const chosen = filters.state === value;
  return (
    <label className={`flex flex-wrap items-center gap-x-[9px] px-2 py-[6px] rounded-control ${
      note ? "text-ink-3" : "cursor-pointer"} ${chosen ? "bg-now-soft text-ink" : ""}`}>
      <input type="radio" name="state" className="accent-action" checked={chosen} disabled={!!note}
             onChange={() => filters.set("state", value ? [value] : [])} />
      {label}<span className={count}>{n.toLocaleString("en")}</span>
      {note && <span className="basis-full pl-[22px] text-[11.5px] text-ink-3">{note}</span>}
    </label>
  );
}
