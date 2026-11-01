import { useState } from "react";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Filters } from "./Filters";
import { FormatFlow } from "./FormatFlow";
import { ModuleTable } from "./ModuleTable";
import { RegistryGraph } from "./RegistryGraph";
import { RegistryTabs } from "./RegistryTabs";
import { SearchBar } from "./SearchBar";
import { Selected } from "./Selected";
import { ago, colourOf, StateIcon, STATES } from "./states";
import type { CataloguePage } from "./useCatalogue";
import { useCatalogue, useFilters } from "./useCatalogue";
import { useSyncNow } from "./useSyncNow";

/** What the registry holds first: that is what a person comes here to compare. */
const ORDERED = [...STATES.filter(({ state }) => state !== "not_imported"),
                 ...STATES.filter(({ state }) => state === "not_imported")];

const MAPS = [["flow", "Format flow"], ["registry", "Your registry"], ["none", "Hide"]] as const;

/** `/registry`: every nf-core module against the registry the builder loads (board 1, forge MVP
 *  part 1). Filters, search and sort live in the address; the selected row too. */
export function Catalogue() {
  useTitle("Registry");
  const filters = useFilters();
  const catalogue = useCatalogue();
  const sync = useSyncNow();
  const [showFilters, setShowFilters] = useState(false);
  const pages = catalogue.data?.pages ?? [];
  const first = pages[0];
  const rows = pages.flatMap((page) => page.rows);
  const selected = rows.find((row) => row.path === filters.module) ?? rows[0];
  const all = Object.values(first?.counts.states ?? {}).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-full bg-paper">
      <RegistryTabs registryAt={first?.registry_at} />
      {catalogue.isPending && <Loading what="the catalogue" />}
      {catalogue.isError && <Failed error={catalogue.error} />}
      {first && !first.last_good && (
        <div className="frame gutter py-[18px] flex flex-col gap-[14px]">
          <div className="catalogue-start">
            <section className="bg-surface border border-line rounded-panel p-[18px] flex flex-col gap-[12px] items-start">
              <h1 className="m-0 text-[18px] font-semibold">Find a tool to add</h1>
              <p className="m-0 text-[13px] text-ink-2 max-w-[62ch]">
                The catalogue has not been synced yet. Comeni reads nf-core's module list and compares
                it with your registry, so you can see what's new and what's out of date. It then
                refreshes daily.
              </p>
              {first.last?.outcome === "failed" && (
                <p className="m-0 text-secondary text-needs-you-ink">The last sync failed: {first.last.error}</p>
              )}
              {first.last?.outcome !== "running" && <SyncNow sync={sync} />}
            </section>
            <section aria-live="polite" className="bg-surface border border-line rounded-panel p-[18px] flex flex-col gap-[12px]">
              <h2 className="m-0 text-[15px] font-semibold">While it reads</h2>
              {first.last?.outcome === "running" ? <Syncing />
                : <p className="m-0 text-[13px] text-ink-3">About 2 minutes. You can leave this page.</p>}
              <p className="mt-auto mb-0 text-[12px] text-ink-3">The list appears here when it's ready.</p>
            </section>
          </div>
        </div>
      )}
      {first && first.last_good && (
        <div className="frame gutter py-[18px] flex flex-col gap-[14px]">
          <SearchBar page={first} rows={rows} />
          <div className="flex flex-wrap justify-between items-center gap-3">
            <div className="seg" role="group" aria-label="Against your registry">
              <button type="button" className="seg-item" aria-pressed={!filters.state} onClick={() => filters.set("state", [])}>
                All modules <span className="font-data text-[12px] text-ink-3">{all.toLocaleString("en")}</span>
              </button>
              {ORDERED.filter(({ state }) => first.counts.states[state] > 0 || state === filters.state).map(({ state, label }) => (
                <button key={state} type="button" className="seg-item" aria-pressed={filters.state === state}
                        onClick={() => filters.set("state", [state])}>
                  <span className={colourOf(state)}><StateIcon state={state} /></span>{label}{" "}
                  <span className="font-data text-[12px] text-ink-3">{(first.counts.states[state] ?? 0).toLocaleString("en")}</span>
                </button>
              ))}
            </div>
            <div className="seg" role="group" aria-label="Picture">
              {MAPS.map(([id, label]) => (
                <button key={id} type="button" className="seg-item" aria-pressed={filters.map === id}
                        onClick={() => filters.set("map", id === "flow" ? [] : [id])}>{label}</button>
              ))}
            </div>
          </div>
          {filters.map === "flow" && <FormatFlow page={first} total={first.total} />}
          {filters.map === "registry" && (
            <RegistryGraph states={Object.fromEntries(rows.map((row) => [row.path, row.state]))} />
          )}
          <div className="catalogue-body">
            <div className="min-w-0">
              <button type="button" className="control lg:hidden mb-2" aria-expanded={showFilters}
                      onClick={() => setShowFilters(!showFilters)}>Filters</button>
              <div className={showFilters ? "block" : "hidden lg:block"}><Filters counts={first.counts} /></div>
            </div>
            <section aria-label="Modules" className="min-w-0 flex flex-col gap-2 self-start">
              <div className="flex flex-wrap justify-between items-center gap-3">
                <p aria-live="polite" className="m-0 text-[13.5px]">
                  <strong className="font-semibold">{first.total.toLocaleString("en")}</strong>{" "}
                  <span className="text-ink-3">{first.total === all ? "nf-core modules" : `of ${all.toLocaleString("en")} modules`}</span>
                </p>
                <label className="inline-flex items-center gap-2 text-[12.5px] text-ink-3">Sort
                  <select aria-label="Sort" value={filters.sort} onChange={(e) => filters.set("sort", [e.target.value])}
                          className="px-2 py-[5px] border border-line-2 rounded-control bg-surface text-ink">
                    <option value="best">Best match</option>
                    <option value="name">Name</option>
                    <option value="upstream_changed">Newest upstream change</option>
                  </select>
                </label>
              </div>
              <ModuleTable rows={rows} selected={selected?.path ?? ""}
                           onSelect={(path) => filters.set("module", [path])}
                           footer={<Footer first={first} shown={rows.length} sync={sync} />} />
              {first.wider > 0 && !filters.mentioned && (
                <p className="m-0 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-2">
                  {first.wider.toLocaleString("en")} more only mention it in a description, because nf-core left the format unstated.
                  <button type="button" className="link-plain" onClick={() => filters.set("mentioned", ["true"])}>Include them</button>
                </p>
              )}
              {filters.mentioned && (
                <p className="m-0 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-2">
                  Including modules that only mention a format in a description.
                  <button type="button" className="link-plain" onClick={() => filters.set("mentioned", [])}>Declared only</button>
                </p>
              )}
              {catalogue.hasNextPage && (
                <button type="button" className="control self-center" onClick={() => catalogue.fetchNextPage()}
                        disabled={catalogue.isFetchingNextPage}>
                  {catalogue.isFetchingNextPage ? "Reading…" : "Show more"}
                </button>
              )}
            </section>
            <div className="min-w-0 self-start lg:sticky lg:top-4"><Selected row={selected} /></div>
          </div>
        </div>
      )}
    </div>
  );
}

function Footer({ first, shown, sync }: {
  first: CataloguePage; shown: number; sync: ReturnType<typeof useSyncNow>;
}) {
  const last = first.last;
  return (
    <>
      <span>{shown.toLocaleString("en")} of {first.total.toLocaleString("en")}</span>
      <span className="flex flex-wrap items-center gap-2">
        {last?.stale
          ? <span className="text-needs-you-ink">Catalogue stale since {ago(last.started_at)}: {last.error}</span>
          : <span>nf-core/modules · synced {first.last_good?.finished_at ? ago(first.last_good.finished_at) : "—"}</span>}
        {last?.outcome === "running" ? <Syncing /> : <SyncNow sync={sync} small />}
      </span>
    </>
  );
}

function Syncing() {
  return <span role="status" className="text-ink-2">Syncing from nf-core…</span>;
}

function SyncNow({ sync, small = false }: { sync: ReturnType<typeof useSyncNow>; small?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={() => sync.mutate()} disabled={sync.isPending}
              className={small
                ? "underline text-action bg-transparent border-0 p-0 cursor-pointer"
                : "px-5 py-[10px] rounded-button bg-action text-on-action font-semibold shadow-raise"}>
        Sync now
      </button>
      {sync.data && !sync.data.queued && <span>A sync is already running.</span>}
      {sync.data?.queued && <span>Sync started.</span>}
      {sync.isError && <Failed error={sync.error} padded={false} />}
    </span>
  );
}
