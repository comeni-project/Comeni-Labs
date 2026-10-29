import { useState } from "react";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Filters } from "./Filters";
import { ModuleTable } from "./ModuleTable";
import { RegistryTabs } from "./RegistryTabs";
import { Selected } from "./Selected";
import { ago } from "./states";
import type { CataloguePage } from "./useCatalogue";
import { useCatalogue, useFilters, useSyncNow } from "./useCatalogue";

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

  return (
    <div className="min-h-full bg-paper-2">
      <RegistryTabs registryAt={first?.registry_at} />
      {catalogue.isPending && <Loading what="the catalogue" />}
      {catalogue.isError && <Failed error={catalogue.error} />}
      {first && !first.last_good && (
        <div className="gutter py-8 flex flex-col items-start gap-3">
          <p className="m-0 text-body">The catalogue has not been synced yet.</p>
          <p className="m-0 text-secondary text-ink-3">
            A sync reads every nf-core module and compares it with the registry. It runs daily;
            this starts one now.
          </p>
          <SyncNow sync={sync} />
        </div>
      )}
      {first && first.last_good && (
        <div className="gutter py-6 flex flex-wrap gap-6 items-start">
          <div className="basis-full lg:basis-[236px] lg:shrink-0">
            <button type="button" className="lg:hidden mb-3 px-4 py-2 border border-line-2 rounded-control bg-surface"
                    aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}>
              Filters
            </button>
            <div className={showFilters ? "block" : "hidden lg:block"}>
              <Filters counts={first.counts} />
            </div>
          </div>
          <section aria-label="Modules" className="flex-[999_1_560px] min-w-0 flex flex-col gap-3">
            <div className="flex flex-wrap gap-[10px] items-center">
              <label htmlFor="catalogue-q" className="sr-only">Search modules</label>
              <input id="catalogue-q" type="search" value={filters.q}
                     placeholder="Search by name, tool, format or what it does"
                     onChange={(e) => filters.set("q", e.target.value ? [e.target.value] : [])}
                     className="flex-[1_1_320px] min-w-0 px-[14px] py-[11px] bg-surface border border-line-2 rounded-control" />
              <label htmlFor="catalogue-sort" className="text-[12.5px] text-ink-2">Sort</label>
              <select id="catalogue-sort" value={filters.sort}
                      onChange={(e) => filters.set("sort", [e.target.value])}
                      className="px-3 py-[10px] border border-line-2 rounded-control bg-surface">
                <option value="best">Best match</option>
                <option value="name">Name</option>
                <option value="upstream_changed">Newest upstream change</option>
              </select>
            </div>
            <ModuleTable rows={rows} selected={selected?.path ?? ""}
                         onSelect={(path) => filters.set("module", [path])}
                         footer={<Footer first={first} shown={rows.length} sync={sync} />} />
            {catalogue.hasNextPage && (
              <button type="button" onClick={() => catalogue.fetchNextPage()}
                      disabled={catalogue.isFetchingNextPage}
                      className="self-center px-4 py-2 border border-line-2 rounded-control bg-surface">
                {catalogue.isFetchingNextPage ? "Reading…" : "Show more"}
              </button>
            )}
          </section>
          <div className="flex-[1_1_320px] max-w-[380px]">
            <Selected row={selected} />
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
        <SyncNow sync={sync} small />
      </span>
    </>
  );
}

function SyncNow({ sync, small = false }: { sync: ReturnType<typeof useSyncNow>; small?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={() => sync.mutate()} disabled={sync.isPending}
              className={small
                ? "underline text-action bg-transparent border-0 p-0 cursor-pointer"
                : "px-5 py-[10px] rounded-button bg-action text-on-action font-semibold"}>
        Sync now
      </button>
      {sync.data && !sync.data.queued && <span>A sync is already running.</span>}
      {sync.data?.queued && <span>Sync started.</span>}
      {sync.isError && <Failed error={sync.error} padded={false} />}
    </span>
  );
}
