import { useEffect, useRef, useState } from "react";

import { get } from "../wiener/api/client";

/** One run's events: page the record, then tail the stream.
 *
 * **The handoff is the only ordering subtlety in the console** — `docs/design/wiener.md` §7.2 —
 * and it is here rather than in a component so there is one implementation of it. A browser
 * that has been closed for a day does not scroll back through Redis: it asks Postgres for a
 * page and subscribes from the id that page ended at.
 *
 * **On close it re-pages rather than reopening blind.** A socket that drops and resubscribes
 * from its last seen id silently misses whatever landed while it was away, and the tail is
 * capped, so "whatever landed" may already have been trimmed. Postgres is the record; asking
 * it again is the only answer that cannot be short.
 */
export type RunEvent = {
  seq: number;
  kind: string;
  at_ms: number;
  trace?: { process: string; status: string; name?: string; realtime_ms?: number | null } | null;
};

type Page = { events: RunEvent[]; cursor: number; stream_id: string };

export type Stream = {
  events: RunEvent[];
  following: boolean;
  error: string | null;
};

export function useRunStream(runId: string | undefined): Stream {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [following, setFollowing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socket = useRef<WebSocket | null>(null);
  /** The highest seq seen, in a ref rather than read out of state.
   *
   * `onclose` fires from a closure created once, so reading `events` there gives whatever the
   * array was when the socket opened — and re-paging from a stale cursor re-fetches everything
   * that arrived while it was connected. */
  const cursor = useRef(-1);

  useEffect(() => {
    if (!runId) return;
    let live = true;

    async function pageThenTail(after: number) {
      const page = await get<Page>(`/api/runs/${runId}/events?after=${after}`);
      if (!live) return;

      setEvents((seen) => {
        const known = new Set(seen.map((e) => e.seq));
        return [...seen, ...page.events.filter((e) => !known.has(e.seq))];
      });
      for (const event of page.events) cursor.current = Math.max(cursor.current, event.seq);

      const url = new URL(`/api/runs/${runId}/stream`, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.searchParams.set("from", page.stream_id);

      const ws = new WebSocket(url.toString());
      socket.current = ws;
      ws.onopen = () => live && setFollowing(true);
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data as string) as RunEvent;
        cursor.current = Math.max(cursor.current, event.seq);
        setEvents((seen) => (seen.some((e) => e.seq === event.seq) ? seen : [...seen, event]));
      };
      ws.onerror = () => live && setError("the live tail dropped");
      ws.onclose = (closed) => {
        if (!live) return;
        setFollowing(false);
        // **1000 means the server drained the run and it is over** — it closes only when the
        // phase is terminal AND the stream is empty. Re-paging on that would open another
        // socket, which would close for the same reason, forever.
        //
        // 4404 is a run this deployment does not have. Anything else — 1006 and friends — is
        // the connection dropping, which is exactly when re-paging is the right answer.
        if (closed.code === 1000 || closed.code === 4404) return;
        void pageThenTail(cursor.current);
      };
    }

    void pageThenTail(-1).catch((e: unknown) => live && setError(String(e)));

    return () => {
      live = false;
      socket.current?.close();
    };
  }, [runId]);

  return { events, following, error };
}
