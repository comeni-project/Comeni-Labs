import { QueryClient } from "@tanstack/react-query";

/** The query client, with defaults chosen rather than inherited.
 *
 * **The cache is trusted, because the mutations keep it correct.** Every write since phase 2
 * invalidates exactly the queries it affects — `useAnswer`, `useAnswerAll`, `usePropose`,
 * `useDecide`, `useAccept`, `useDraft`. With that in place TanStack's defaults
 * (`staleTime: 0`, `refetchOnWindowFocus: true`) were not protecting correctness; they were
 * refetching on every navigation and every alt-tab, against endpoints that took 250ms.
 * Audit A137.
 *
 * **30 seconds rather than forever.** The registry moves under the tool — the nightly check, a
 * `forge land` in a terminal, a colleague's commit — so a screen left open catches up on its
 * own. It is a tool, so the window can be generous; it is not single-user, so not unbounded.
 * This is the one number here that is a judgement rather than a measurement, and the first
 * that should move once somebody has used it for an afternoon.
 *
 * **Extracted from `main.tsx` so a test can call it.** That file mounts React as a side
 * effect of being imported, so the defaults could not otherwise be asserted.
 */
export function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
      },
    },
  });
}
