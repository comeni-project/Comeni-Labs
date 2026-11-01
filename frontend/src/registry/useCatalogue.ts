import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import type { State } from "./states";

export type CataloguePage = components["schemas"]["CataloguePage"];
export type ModuleRow = components["schemas"]["ModuleRow"];
export type ModuleDetail = components["schemas"]["ModuleDetail"];
export type FormatLink = components["schemas"]["FormatLink"];

const PER_PAGE = 50;

/** The catalogue's filters live in the address, so a view can be linked and survives a reload.
 *  `module` is the selected row; `map` is which picture is open. */
export function useFilters() {
  const [params, setParams] = useSearchParams();
  const change = (apply: (next: URLSearchParams) => void) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      apply(next);
      return next;
    }, { replace: true });
  const set = (key: string, values: string[]) => change((next) => {
    next.delete(key);
    for (const value of values) next.append(key, value);
  });
  return {
    state: (params.get("state") ?? "") as State | "",
    topics: params.getAll("topic"),
    noTopic: params.get("no_topic") === "true",
    suites: params.getAll("suite"),
    reads: params.getAll("reads"),
    makes: params.getAll("makes"),
    mentioned: params.get("mentioned") === "true",
    q: params.get("q") ?? "",
    sort: params.get("sort") ?? "best",
    module: params.get("module") ?? "",
    map: params.get("map") ?? "flow",
    set,
    change,
  };
}

type Filters = ReturnType<typeof useFilters>;

function shared(filters: Filters): URLSearchParams {
  const query = new URLSearchParams();
  if (filters.state) query.set("state", filters.state);
  for (const topic of filters.topics) query.append("topic", topic);
  if (filters.noTopic) query.set("no_topic", "true");
  for (const suite of filters.suites) query.append("suite", suite);
  if (filters.mentioned) query.set("mentioned", "true");
  if (filters.q.trim()) query.set("q", filters.q.trim());
  return query;
}

export function useCatalogue() {
  const filters = useFilters();
  const query = shared(filters);
  for (const format of filters.reads) query.append("reads", format);
  for (const format of filters.makes) query.append("makes", format);
  query.set("sort", filters.sort);
  query.set("limit", String(PER_PAGE));
  return useInfiniteQuery({
    queryKey: ["catalogue", query.toString()],
    queryFn: ({ pageParam }) => {
      const page = new URLSearchParams(query);
      page.set("offset", String(pageParam));
      return get<CataloguePage>(`/forge/catalogue?${page.toString()}`);
    },
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    placeholderData: keepPreviousData,
    // While a sync runs, read again until it ends, so the page shows it finish (or fail).
    refetchInterval: (query) =>
      query.state.data?.pages[0]?.last?.outcome === "running" ? 2_000 : false,
  });
}

/** How the formats on show connect, under the same filters. */
export function useFlow(reads: string[], makes: string[]) {
  const filters = useFilters();
  const query = shared(filters);
  for (const format of reads) query.append("show_reads", format);
  for (const format of makes) query.append("show_makes", format);
  return useQuery({
    queryKey: ["catalogue-flow", query.toString()],
    queryFn: () => get<FormatLink[]>(`/forge/catalogue/flow?${query.toString()}`),
    enabled: reads.length > 0 && makes.length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useModuleDetail(row: ModuleRow | undefined) {
  return useQuery({
    queryKey: ["catalogue-module", row?.source, row?.path],
    queryFn: () => get<ModuleDetail>(`/forge/catalogue/${row?.source}/${row?.path}`),
    enabled: row !== undefined,
  });
}
