import { useState } from "react";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { ToolFilters } from "./ToolFilters";
import { FormatFlow } from "./FormatFlow";
import { ModuleTable } from "./ModuleTable";
import { RegistryTabs } from "./RegistryTabs";
import { SearchBar } from "./SearchBar";
import { Selected } from "./Selected";
import { ago } from "./states";
import type { CataloguePage } from "./useCatalogue";
import { useCatalogue, useFilters } from "./useCatalogue";
import { useSyncNow } from "./useSyncNow";

/** `/registry` · **Tools** (board "7 · Registry", #511): search with the filters on as chips; the
 *  formats overview across the page; then one workspace of three columns — filters, the tool list
 *  and the selected tool's card — each pinned beside the others and scrolling on its own. Narrower,
 *  the filters fold behind a toggle above the list. Filters, search, sort and the selected tool
 *  live in the address. */
export function Catalogue() {
  useTitle("Registry");
  const filters = useFilters();
  const catalogue = useCatalogue();
  const sync = useSyncNow();
  const pages = catalogue.data?.pages ?? [];
  const first = pages[0];
  const rows = pages.flatMap((page) => page.rows);
  const selected = rows.find((row) => row.path === filters.module) ?? rows[0];
  const filtered = !!(filters.q.trim() || filters.states.length || filters.sources.length || filters.suites.length
    || filters.topics.length || filters.reads.length || filters.makes.length);
  const [filtersOpen, setFiltersOpen] = useState(false);

  return (
    <div className="reg overflow-y-auto h-full">
      <RegistryTabs />
      <div className="page reg-page">
      {catalogue.isPending && <Loading what="the catalogue" />}
      {catalogue.isError && <Failed error={catalogue.error} />}
      {first && !first.last_good && (
        <div className="catalogue-start">
          <section className="bg-surface border border-line rounded-panel p-[18px] flex flex-col gap-[12px] items-start">
            <h1 className="m-0 text-[18px] font-semibold">Find a tool to add</h1>
            <p className="m-0 text-[13px] text-ink-2 max-w-[62ch]">
              The catalogue has not been synced yet: it is read from nf-core once, then every day.
            </p>
            {first.last?.outcome === "failed" && (
              <p className="m-0 text-secondary text-needs-you-ink">The last sync failed: {first.last.error}</p>
            )}
            {first.last?.outcome !== "running" && <SyncNow sync={sync} />}
          </section>
          <section aria-live="polite" className="bg-surface border border-line rounded-panel p-[18px] flex flex-col gap-[12px]">
            {first.last?.outcome === "running" ? <Syncing /> : <p className="m-0 text-[13px] text-ink-3">About 10 seconds.</p>}
          </section>
        </div>
      )}
      {first && first.last_good && (
        <>
          <SearchBar page={first} rows={rows} />
          <FormatFlow page={first} total={first.total} />
          <div className={`reg-work ${filtersOpen ? "has-filters-open" : ""}`}>
            <ToolFilters page={first} open={filtersOpen} onToggle={() => setFiltersOpen(!filtersOpen)} />
            <section aria-label="Modules" className="reg-col reg-list">
              <ModuleTable rows={rows} selected={selected?.path ?? ""}
                           onSelect={(path) => filters.set("module", [path])}
                           header={<>
                             <p aria-live="polite" className="m-0 text-[13.5px] min-w-0">
                               <strong className="font-semibold">{filtered ? "Matches" : "Best matches"}</strong>{" "}
                               <span className="text-ink-3">{rows.length.toLocaleString("en")}{first.total > rows.length ? ` of ${first.total.toLocaleString("en")}` : ""}</span>
                             </p>
                             <select aria-label="Sort" value={filters.sort} onChange={(e) => filters.set("sort", [e.target.value])}
                                     className="ml-auto px-2 py-[5px] border border-line-2 rounded-control bg-surface text-[12.5px] text-ink">
                               <option value="best">Fits your registry</option>
                               <option value="name">Name</option>
                               <option value="upstream_changed">Newest upstream</option>
                             </select>
                           </>}
                           notice={first.wider > 0 && !filters.mentioned ? (
                             <>
                               {first.wider.toLocaleString("en")} more only mention it in a description.
                               <button type="button" className="link-plain" onClick={() => filters.set("mentioned", ["true"])}>Include them</button>
                             </>
                           ) : filters.mentioned ? (
                             <>
                               Including tools that only mention a format in a description.
                               <button type="button" className="link-plain" onClick={() => filters.set("mentioned", [])}>Declared only</button>
                             </>
                           ) : null}
                           more={catalogue.hasNextPage ? (
                             <button type="button" className="control self-center my-3" onClick={() => catalogue.fetchNextPage()}
                                     disabled={catalogue.isFetchingNextPage}>
                               {catalogue.isFetchingNextPage ? "Reading…" : "Show more"}
                             </button>
                           ) : null}
                           footer={<Footer first={first} shown={rows.length} sync={sync} />} />
            </section>
            <div className="reg-col reg-detail"><Selected row={selected} /></div>
          </div>
        </>
      )}
      </div>
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
