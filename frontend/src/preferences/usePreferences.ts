import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, put } from "../api/client";
import type { components } from "../api/schema";
import { get as wienerGet } from "../wiener/api/client";

export type Menu = components["schemas"]["Menu"];
export type Entry = components["schemas"]["Entry"];
export type Shown = components["schemas"]["Shown"];

/** Every section the API serves. **Never cached past a write**: the menu always shows what the
 *  server would resolve now, including a lock `.env` added since the page opened. */
export function useMenu() {
  return useQuery({ queryKey: ["settings"], queryFn: () => get<Menu>("/settings") });
}

export function useWrite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      put<Shown>(`/settings/${encodeURIComponent(key)}`, { value }),
    onSettled: () => client.invalidateQueries({ queryKey: ["settings"] }),
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
