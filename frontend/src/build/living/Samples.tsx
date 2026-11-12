import { useMemo, useState } from "react";

import type { components } from "../../api/schema";

type Sample = components["schemas"]["UploadedSample"];

/** Every sample of the last upload, with what was measured on it (issue 466): hundreds of
 *  rows, sorted by any measurement, filtered by name, and grouped by one measurement to see how
 *  the samples spread. Choosing one value or a split is the question card's, which the spread
 *  pre-fills; this table is for looking. */
export function Samples({ samples, pageSize = 50 }: { samples: Sample[]; pageSize?: number }) {
  const measurements = useMemo(
    () => [...new Set(samples.flatMap((s) => s.facts.map((f) => f.measurement)))].sort(),
    [samples],
  );
  const [filter, setFilter] = useState("");
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<string>("");
  const [page, setPage] = useState(0);

  const valueOf = (sample: Sample, measurement: string) => {
    const fact = sample.facts.find((f) => f.measurement === measurement);
    return fact?.value === undefined || fact?.value === null ? "" : String(fact.value);
  };

  const shown = useMemo(() => {
    const kept = samples.filter((s) => s.name.toLowerCase().includes(filter.trim().toLowerCase()));
    if (!sortBy) return kept;
    return [...kept].sort((a, b) =>
      valueOf(a, sortBy).localeCompare(valueOf(b, sortBy), undefined, { numeric: true }));
  }, [samples, filter, sortBy]);

  const groups = useMemo(() => {
    if (!groupBy) return [];
    const counts = new Map<string, number>();
    for (const sample of shown) {
      const value = valueOf(sample, groupBy) || "not measured";
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [shown, groupBy]);

  if (samples.length === 0) return null;
  const pages = Math.max(1, Math.ceil(shown.length / pageSize));
  const rows = shown.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <section aria-label="your samples" className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-center gap-3 text-secondary text-ink-2">
        <span className="text-label text-ink-3">{samples.length} samples</span>
        <input aria-label="filter samples by name" value={filter} placeholder="filter by name"
               onChange={(e) => { setFilter(e.target.value); setPage(0); }}
               className="px-2 py-1 bg-surface border border-line rounded-control text-body" />
        <label className="flex items-center gap-1">
          group by
          <select aria-label="group samples by" value={groupBy}
                  onChange={(e) => setGroupBy(e.target.value)}
                  className="px-2 py-1 bg-surface border border-line rounded-control text-body">
            <option value="">nothing</option>
            {measurements.map((m) => <option key={m} value={m}>{m.replace(/_/g, " ")}</option>)}
          </select>
        </label>
      </div>
      {groupBy && (
        <ul aria-label={`samples by ${groupBy}`} className="flex flex-wrap gap-2">
          {groups.map(([value, count]) => (
            <li key={value} data-testid="sample-group" className="chip chip-plain">
              {value}: {count}
            </li>
          ))}
        </ul>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-secondary">
          <thead>
            <tr>
              <th className="text-left text-label text-ink-3 font-normal pr-3">sample</th>
              {measurements.map((m) => (
                <th key={m} className="text-left text-label text-ink-3 font-normal pr-3">
                  <button type="button" onClick={() => setSortBy(m)}
                          className="bg-transparent border-0 p-0 text-label text-ink-3 cursor-pointer">
                    {m.replace(/_/g, " ")}{sortBy === m ? " ↑" : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((sample) => (
              <tr key={sample.name} data-testid="sample-row" title={sample.files.join(", ")}>
                <td className="font-data text-ink pr-3">{sample.name}</td>
                {measurements.map((m) => (
                  <td key={m} className="font-data text-ink-2 pr-3">{valueOf(sample, m) || "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center gap-2 text-secondary text-ink-3">
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}
                  className="px-2 py-1 border border-line-2 bg-transparent cursor-pointer">previous</button>
          <span>page {page + 1} of {pages}</span>
          <button type="button" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}
                  className="px-2 py-1 border border-line-2 bg-transparent cursor-pointer">next</button>
        </div>
      )}
    </section>
  );
}
