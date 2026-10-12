import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, put } from "../api/client";
import type { components } from "../api/schema";
import { get as wienerGet, put as wienerPut } from "../wiener/api/client";

export type Menu = components["schemas"]["Menu"];
export type Entry = components["schemas"]["Entry"];
export type Shown = components["schemas"]["Shown"];

/** Every section the API serves. **Never cached past a write**: the menu always shows what the
 *  server would resolve now, including a lock `.env` added since the page opened. */
export function useMenu() {
  return useQuery({ queryKey: ["settings"], queryFn: () => get<Menu>("/settings") });
}

export type Server = "mendel" | "wiener";

/** A change, sent to **the server that serves its section**: Mendel's own, or Wiener's for a
 *  section Wiener stores (Data retention: runs, Part H). Both menus share the `settings` key, so
 *  either write asks for both again. */
export function useWrite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value, served = "mendel" }: { key: string; value: unknown;
                                                       served?: Server }) =>
      served === "wiener"
        ? wienerPut<Shown>(`/api/wiener/settings/${encodeURIComponent(key)}`, { value })
        : put<Shown>(`/settings/${encodeURIComponent(key)}`, { value }),
    onSettled: () => client.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export type LastSweep = { ran_at: string; removed: Record<string, number> } | null;

/** When retention last ran on one server, and what it removed (Part H): the line under a Data
 *  retention section that says the limits are being kept. */
export function useLastSweep(served: Server, enabled: boolean) {
  return useQuery({
    queryKey: ["settings", "retention-last", served],
    queryFn: () => served === "wiener"
      ? wienerGet<LastSweep>("/api/wiener/retention/last")
      : get<LastSweep>("/settings/retention/last"),
    enabled,
    retry: false,
  });
}

/** Running comes from Wiener, which reads its own `.env` (spec §7). Its own query, so a Wiener
 *  that is down or wants a token costs one section, not the page. */
export function useWienerMenu() {
  return useQuery({
    queryKey: ["settings", "wiener"],
    queryFn: () => wienerGet<Menu>("/api/wiener/settings"),
    retry: false,
  });
}
