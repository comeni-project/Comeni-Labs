import { CheckList, type CheckOption } from "../ui/CheckList";
import { FORMAT_WORDS } from "./FormatFlow";
import { labelOf, StateDot, type State } from "./states";
import type { CataloguePage } from "./useCatalogue";
import { useFilters } from "./useCatalogue";

/** The states in the board's order; one with nothing in it is left out unless ticked. */
const STATES = ["imported", "update_available", "merged_not_released", "in_review", "unknown", "gone_upstream", "not_imported"] as const;
const SOURCES: Record<string, string> = { "nf-core": "nf-core", pegi3s: "pegi3s · preview" };

const byCount = (counts: Record<string, number>, on: string[]) =>
  Object.entries(counts).filter(([id, n]) => n > 0 || on.includes(id)).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

/** **Registry · Tools' filters** (2026-11-17), a panel as Run → Outputs has: where tools come
 *  from, how they stand against your registry, the formats they take and make, their topic and
 *  their tool family — each a tick list with the catalogue's counts, all in the address. */
export function ToolFilters({ page }: { page: CataloguePage }) {
  const filters = useFilters();
  const flip = (key: string, list: string[], id: string) =>
    filters.set(key, list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const list = (counts: Record<string, number>, on: string[], word: (id: string) => string = (id) => id): CheckOption[] =>
    byCount(counts, on).map(([id, n]) => ({ id, label: word(id), text: `${id} ${word(id)}`, count: n, on: on.includes(id) }));
  const format = (id: string) => (FORMAT_WORDS[id] ? `${id} · ${FORMAT_WORDS[id]}` : id);
  const states: CheckOption[] = STATES.filter((s) => (page.counts.states[s] ?? 0) > 0 || filters.states.includes(s))
    .map((s) => ({ id: s, label: <span className="inline-flex items-center gap-[6px]"><StateDot state={s as State} />{labelOf(s as State)}</span>,
                   text: labelOf(s as State), count: page.counts.states[s] ?? 0, on: filters.states.includes(s) }));

  return (
    <aside aria-label="Filters" className="flex flex-col gap-4 p-4 bg-surface border border-line rounded-panel min-w-0
                                           lg:sticky lg:top-4 lg:max-h-[calc(100dvh-32px)] lg:overflow-y-auto">
      <CheckList title="Source" options={list(page.counts.sources, filters.sources, (id) => SOURCES[id] ?? id)}
                 onFlip={(id) => flip("source", filters.sources, id)} />
      <CheckList title="In your registry" options={states} onFlip={(id) => flip("state", filters.states, id)} />
      <CheckList title="Takes" options={list(page.counts.reads, filters.reads, format)} onFlip={(id) => flip("reads", filters.reads, id)} />
      <CheckList title="Makes" options={list(page.counts.makes, filters.makes, format)} onFlip={(id) => flip("makes", filters.makes, id)} />
      <CheckList title="Topic" options={list(page.counts.topics, filters.topics)} onFlip={(id) => flip("topic", filters.topics, id)} />
      <CheckList title="Tool family" options={list(page.counts.suites, filters.suites)} onFlip={(id) => flip("suite", filters.suites, id)} />
    </aside>
  );
}
