import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import type { State } from "./states";

export type CataloguePage = components["schemas"]["CataloguePage"];
export type ModuleRow = components["schemas"]["ModuleRow"];

const PER_PAGE = 50;

/** The catalogue's filters live in the address (`?state=…&topic=…&q=…`), so a view can be linked
 *  and survives a reload. `module` is the selected row. */
export function useFilters() {
  const [params, setParams] = useSearchParams();
  const set = (key: string, values: string[]) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete(key);
      for (const value of values) next.append(key, value);
      return next;
    }, { replace: true });
  return {
    state: (params.get("state") ?? "") as State | "",
    topics: params.getAll("topic"),
    formats: params.getAll("format"),
    q: params.get("q") ?? "",
    sort: params.get("sort") ?? "best",
    module: params.get("module") ?? "",
    set,
  };
}

export function useCatalogue() {
  const { state, topics, formats, q, sort } = useFilters();
  const query = new URLSearchParams();
  if (state) query.set("state", state);
  for (const topic of topics) query.append("topic", topic);
  for (const format of formats) query.append("format", format);
  if (q.trim()) query.set("q", q.trim());
  query.set("sort", sort);
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
