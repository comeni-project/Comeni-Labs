/** Starting a gate, and watching it.
 *
 * **This is the one place polling is right**, and it is worth saying why given 3E's flicker.
 * There the server seeded and the client owned, because the client knew the answer and asking
 * again produced a worse one. A gate is the opposite: the state lives on the server, takes
 * between a minute and an hour, and the browser genuinely cannot know it. So it asks — and
 * stops the moment the run is terminal, because a finished run polled forever is exactly the
 * spam this project asked not to ship.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get, post } from "../api/client";
import type { GateView } from "../api/types";

const LIVE = ["queued", "running"];

export function useGate(draftId: string | null) {
  const [runId, setRunId] = useState<string | null>(null);

  const run = useQuery({
    queryKey: ["gate", runId],
    // A plain template string: `client.ts` is a hand-written wrapper taking a path, not
    // openapi-fetch — there is no `{ params: { path } }` here. The `/pipeline` prefix is the
    // router's; `ROOT = "/api"` in that file supplies the rest.
    queryFn: () => get<GateView>(`/pipeline/gates/${runId}`),
    enabled: runId !== null,
    refetchInterval: (q) => (q.state.data && LIVE.includes(q.state.data.state) ? 2000 : false),
  });

  /** Which gate was asked for. **Not derivable from `run`**: between the click and the first
   *  poll there is no run to read a name off, and that gap is most of a second. */
  const [asked, setAsked] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: (gate: string) => {
      setAsked(gate);
      return post<GateView>(`/pipeline/drafts/${draftId}/gate`, { gate });
    },
    onSuccess: (started) => setRunId(started.id),
    onError: () => setAsked(null),
  });

  const running = start.isPending || (run.data ? LIVE.includes(run.data.state) : false);

  return {
    run: run.data ?? null,
    /** The gate currently in flight, or `null`. The control labels *that* button rather than
     *  assuming the first one — pressing Preview used to put "Gating…" on Lint. */
    active: running ? (run.data?.gate ?? asked) : null,
    start: (gate: string) => start.mutate(gate),
    error: start.error ? String(start.error.message) : null,
    // `queued` and `running` both count: the button must not offer a second gate while one is
    // in flight, and `start.isPending` alone goes false the moment the POST returns.
    running,
  };
}
