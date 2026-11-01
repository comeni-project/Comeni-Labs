import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { get } from "../../api/client";
import type { Step } from "./progress";

const merged = (known: Step[], arrived: Step) =>
  (known.some((s) => s.seq === arrived.seq) ? known : [...known, arrived]);

/** What the AI has done on this adaptation. The record is read once, then followed while it works.
 *  If the stream drops or the browser has none, it polls the same record, so nothing is missed. */
export function useForgeSteps(id: string, working: boolean): Step[] {
  const client = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const key = ["forge-steps", id];
  const record = useQuery({
    queryKey: key,
    queryFn: () => get<Step[]>(`/forge/adaptations/${id}/events`),
    refetchInterval: working && !streaming ? 2_000 : false,
  });
  const after = record.data?.at(-1)?.seq ?? 0;
  const ready = record.isSuccess;

  useEffect(() => {
    if (!working || !ready || typeof EventSource === "undefined") return;
    const source = new EventSource(`/api/forge/adaptations/${id}/events/stream?after=${after}`);
    setStreaming(true);
    const stop = () => { source.close(); setStreaming(false); };
    source.onmessage = (event) => {
      client.setQueryData<Step[]>(key, (known = []) => merged(known, JSON.parse(event.data) as Step));
    };
    source.addEventListener("end", () => {
      stop();
      void client.invalidateQueries({ queryKey: ["adaptation", id] });
    });
    source.onerror = stop;
    return stop;
    // `after` only seeds the stream: following it would reopen the stream on every step.
  }, [id, working, ready]);

  return record.data ?? [];
}
