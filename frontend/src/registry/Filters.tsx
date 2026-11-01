import { useState } from "react";

import type { CataloguePage } from "./useCatalogue";
import { useFilters } from "./useCatalogue";

const SUITES_SHOWN = 8;

function Bar({ label, n, most, on, mono = false, onClick }: {
  label: string; n: number; most: number; on: boolean; mono?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" className="bar" aria-pressed={on} data-empty={n === 0} onClick={onClick}>
      <span className="bar-fill" style={{ width: `${(n / most) * 100}%` }} />
      <span className={`bar-label ${mono ? "font-data text-[12.5px]" : ""}`}>{label}</span>
      <span className="bar-count">{n.toLocaleString("en")}</span>
    </button>
  );
}

const named = (topic: string) => topic.charAt(0).toUpperCase() + topic.slice(1);

/** The left rail: each bar shows what choosing it would show. Nearly half of nf-core's modules
 *  carry no topic, so that row stays, and every module has a suite. */
export function Filters({ counts }: { counts: CataloguePage["counts"] }) {
  const filters = useFilters();
  const [find, setFind] = useState("");
  const toggle = (key: string, list: string[], value: string) =>
    filters.set(key, list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  const topics = Object.entries(counts.topics).sort((a, b) => b[1] - a[1]);
  const topicMost = Math.max(1, counts.no_topic, ...topics.map(([, n]) => n));
  const wanted = find.trim().toLowerCase();
  const allSuites = Object.entries(counts.suites).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const matching = allSuites.filter(([suite]) => !wanted || suite.includes(wanted));
  const suites = [
    ...filters.suites.filter((s) => !matching.slice(0, SUITES_SHOWN).some(([x]) => x === s))
      .map((s): [string, number] => [s, counts.suites[s] ?? 0]),
    ...matching,
  ].slice(0, SUITES_SHOWN);
  const suiteMost = Math.max(1, ...suites.map(([, n]) => n));

  return (
    <aside aria-label="Filters" className="flex flex-col gap-4 min-w-0">
      <div>
        <p className="m-0 mb-[5px] text-[12px] text-ink-3">Topic</p>
        {topics.map(([topic, n]) => (
          <Bar key={topic} label={named(topic)} n={n} most={topicMost} on={filters.topics.includes(topic)}
               onClick={() => toggle("topic", filters.topics, topic)} />
        ))}
        <Bar label="No topic" n={counts.no_topic} most={topicMost} on={filters.noTopic}
             onClick={() => filters.set("no_topic", filters.noTopic ? [] : ["true"])} />
      </div>
      <div>
        <p className="m-0 mb-[5px] flex justify-between text-[12px] text-ink-3">
          <span>Tool suite</span><span>{allSuites.length.toLocaleString("en")}</span>
        </p>
        <input type="search" aria-label="Find a suite" value={find} placeholder="Find a suite" autoComplete="off"
               onChange={(event) => setFind(event.target.value)} className="facet-find" />
        {suites.map(([suite, n]) => (
          <Bar key={suite} label={suite} n={n} most={suiteMost} mono on={filters.suites.includes(suite)}
               onClick={() => toggle("suite", filters.suites, suite)} />
        ))}
      </div>
    </aside>
  );
}
