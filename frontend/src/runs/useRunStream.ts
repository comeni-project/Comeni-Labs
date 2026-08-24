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

/** What one request asks for, and therefore what a FULL page looks like.
 *
 * The endpoint's own default is 200 and the loop below compares against this number, so it is
 * sent explicitly rather than relied on: a server that changed its default would otherwise
 * turn "a full page" into a wrong guess and stop the drain early — silently, which is the
 * failure mode this whole change is about.
 */
const PAGE = 200;

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
  /** Events that have arrived since the last flush, and the frame that will flush them. */
  const arriving = useRef<RunEvent[]>([]);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) return;
    let live = true;

    async function pageThenTail(after: number) {
      // **Drain the record before subscribing.** It used to page ONCE and subscribe, so a
      // reload mid-run showed the first 200 events and then a silent hole — and nothing
      // noticed, because the largest real run is five tasks and every run fitted in one page.
      //
      // A short page is the end of the record. Subscribing earlier would tail live events
      // while pages 2 and 3 were still arriving, which is the same hole from the other side.
      let page: Page;
      let from = after;
      do {
        page = await get<Page>(`/api/runs/${runId}/events?after=${from}&limit=${PAGE}`);
        if (!live) return;

        // **`arrived` is a const, and `page` is not.** React runs a functional update LATER,
        // so an updater closing over the loop's mutable `page` reads whichever page has
        // arrived by then — which silently merged page 3 twice and dropped page 2 entirely.
        // Found by the drain test expecting 437 and getting 237.
        const arrived = page.events;
        setEvents((seen) => {
          const known = new Set(seen.map((e) => e.seq));
          return [...seen, ...arrived.filter((e) => !known.has(e.seq))];
        });
        for (const event of arrived) cursor.current = Math.max(cursor.current, event.seq);
        from = page.cursor;
      } while (page.events.length === PAGE);

      const url = new URL(`/api/runs/${runId}/stream`, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.searchParams.set("from", page.stream_id);

      const ws = new WebSocket(url.toString());
      socket.current = ws;
      ws.onopen = () => live && setFollowing(true);
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data as string) as RunEvent;
        cursor.current = Math.max(cursor.current, event.seq);
        // **One state write per frame, not one per message** — A199. `setEvents((seen) =>
        // [...seen, event])` copies the whole array per event, so a 5,000-task run's tail
        // degrades quadratically: the console gets slower the longer you watch it, which is
        // the opposite of what this slice promises. Buffering turns a burst of n messages
        // into one copy.
        arriving.current.push(event);
        if (frame.current === null) {
          frame.current = requestAnimationFrame(() => {
            frame.current = null;
            const batch = arriving.current;
            arriving.current = [];
            if (!live || batch.length === 0) return;
            setEvents((seen) => {
              const known = new Set(seen.map((e) => e.seq));
              const fresh = batch.filter((e) => !known.has(e.seq));
              return fresh.length ? [...seen, ...fresh] : seen;
            });
          });
        }
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
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
      arriving.current = [];
      socket.current?.close();
    };
  }, [runId]);

  return { events, following, error };
}
