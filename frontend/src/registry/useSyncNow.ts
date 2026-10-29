import { useMutation, useQueryClient } from "@tanstack/react-query";

import { post } from "../api/client";

/** *Sync now*. `queued: false` means one is already running; either way the page re-reads. */
export function useSyncNow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => post<{ queued: boolean }>("/forge/catalogue/sync", {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["catalogue"] }),
  });
}
