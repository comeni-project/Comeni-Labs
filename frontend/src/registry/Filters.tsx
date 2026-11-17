import type { CataloguePage } from "./useCatalogue";
import { useFilters } from "./useCatalogue";

const named = (topic: string) => topic.charAt(0).toUpperCase() + topic.slice(1);

/** **Topic, in the rail** (board "7 · Registry"): one bar a topic, its fill the share of tools,
 *  picked ones filled; picking filters the list and the flow. */
export function Filters({ counts }: { counts: CataloguePage["counts"] }) {
  const filters = useFilters();
  const topics = Object.entries(counts.topics).sort((a, b) => b[1] - a[1]);
  const most = Math.max(1, ...topics.map(([, n]) => n));
  const toggle = (topic: string) => filters.set("topic", filters.topics.includes(topic)
    ? filters.topics.filter((t) => t !== topic) : [...filters.topics, topic]);
  return (
    <div role="group" aria-label="Topics" className="flex flex-col gap-[2px]">
      {topics.map(([topic, n]) => {
        const on = filters.topics.includes(topic);
        return (
          <button key={topic} type="button" aria-pressed={on} onClick={() => toggle(topic)}
                  className={`relative flex items-center gap-2 h-[26px] px-[10px] rounded-control border-0 text-left text-[12.5px] cursor-pointer
                              ${on ? "text-now-ink font-semibold" : "text-ink-2 hover:text-ink"} bg-transparent`}>
            <span aria-hidden="true" className={`absolute inset-y-[2px] left-0 rounded-control ${on ? "bg-now-soft" : "bg-surface-2"}`}
                  style={{ width: `${Math.max(8, (100 * n) / most)}%` }} />
            <span className="relative truncate">{named(topic)}</span>
            <span className="relative ml-auto text-[11.5px] text-ink-3 tabular-nums">{n.toLocaleString("en")}</span>
          </button>
        );
      })}
    </div>
  );
}
