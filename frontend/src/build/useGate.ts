/** Starting a gate, and watching it.
 *
 * **This is the one place polling is right**, and it is worth saying why given 3E's flicker.
 * There the server seeded and the client owned, because the client knew the answer and asking
 * again produced a worse one. A gate is the opposite: the state lives on the server, takes
 * between a minute and an hour, and the browser genuinely cannot know it. So it asks — and
 * stops the moment the run is terminal, because a finished run polled forever is exactly the
 * spam this project asked not to ship.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post } from "../api/client";
import type { GateView } from "../api/types";

const LIVE = ["queued", "running"];

type Current = { runId: string | null; asked: string | null; pending: boolean };

const NOTHING: Current = { runId: null, asked: null, pending: false };

export function useGate(draftId: string | null) {
  /** **Which gate is in flight lives in the query cache, not in `useState`** — and that is a
   *  fix rather than a style.
   *
   *  `Gate` and `GatePanel` each call this hook, and `GatePanel` renders a `Gate` inside
   *  itself, so there are two instances on screen at once: the toolbar's and the panel's. With
   *  the run id in component state they were two independent gates — press the toolbar button
   *  and the panel showed no progress, no state and **no output**, because its own `runId` was
   *  still `null` and its poll was disabled. The tab looked broken and nothing was.
   *
   *  A cache entry keyed by the draft is shared by every observer, so both instances see one
   *  gate. Found by wiring *Run this* to `gate.run.state` and asking which of the two it would
   *  have been reading.
   */
  const client = useQueryClient();
  const key = ["gate-current", draftId ?? ""];
  const current = useQuery<Current>({
    queryKey: key,
    // Never fetched: this is state that happens to live where both instances can see it.
    queryFn: () => NOTHING,
    enabled: false,
    initialData: NOTHING,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  const { runId, asked } = current.data;
  /** **Always a function of the previous value.** `asked` is written by `mutationFn` and
   *  `runId` by `onSuccess`, and both callbacks close over the render they were created in —
   *  so an object built from the closure's `asked` puts back the value from *before* the
   *  click. The updater form reads the cache at the moment it writes. */
  const put = (next: (prev: Current) => Current) =>
    client.setQueryData<Current>(key, (prev) => next(prev ?? NOTHING));

  const run = useQuery({
    queryKey: ["gate", runId],
    // A plain template string: `client.ts` is a hand-written wrapper taking a path, not
    // openapi-fetch — there is no `{ params: { path } }` here. The `/pipeline` prefix is the
    // router's; `ROOT = "/api"` in that file supplies the rest.
    queryFn: () => get<GateView>(`/pipeline/gates/${runId}`),
    enabled: runId !== null,
    refetchInterval: (q) => (q.state.data && LIVE.includes(q.state.data.state) ? 2000 : false),
  });

  /** `asked` is which gate was asked for. **Not derivable from `run`**: between the click and
   *  the first poll there is no run to read a name off, and that gap is most of a second. */
  const start = useMutation({
    mutationFn: (gate: string) => {
      put((prev) => ({ ...prev, asked: gate, pending: true }));
      return post<GateView>(`/pipeline/drafts/${draftId}/gate`, { gate });
    },
    onSuccess: (started) => put((prev) => ({ ...prev, runId: started.id, pending: false })),
    onError: () => put((prev) => ({ ...prev, asked: null, pending: false })),
  });

  /** **`pending` is in the cache and `start.isPending` is not**, which is the difference
   *  between one gate seen from two places and two gates. `isPending` belongs to the mutation
   *  the instance owns, so the toolbar knew it had asked and the panel did not — for the whole
   *  second before the POST answers, and then again for the gap between the answer and the
   *  first poll. Both windows are exactly when somebody is looking to see whether it worked.
   *
   *  The second clause reads `runId` rather than `run.data`: between the run being accepted
   *  and the first poll landing there is a run and no state, and *no state yet* is running. */
  const running =
    current.data.pending ||
    (runId !== null && (run.data ? LIVE.includes(run.data.state) : true));

  return {
    run: run.data ?? null,
    /** The gate currently in flight, or `null`. The control labels *that* button rather than
     *  assuming the first one — pressing Preview used to put "Gating…" on Lint. */
    active: running ? (run.data?.gate ?? asked) : null,
    start: (gate: string) => start.mutate(gate),
    /** **A gate that passed, on the pipeline as it stands.** `blocked` is what says the graph
     *  moved since it was kept; this says the last gate on the kept version came back green.
     *  It is what unlocks *Run this*, and it is deliberately not "a gate has been run". */
    passed: run.data?.state === "passed",
    error: start.error ? String(start.error.message) : null,
    // `queued` and `running` both count: the button must not offer a second gate while one is
    // in flight, and `start.isPending` alone goes false the moment the POST returns.
    running,
  };
}
