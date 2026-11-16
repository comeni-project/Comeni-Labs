import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useRunStream } from "./useRunStream";

class FakeSocket {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(url: string) {
    this.url = url;
    sockets.push(this);
    queueMicrotask(() => this.onopen?.());
  }
  close() {}
}
const sockets: FakeSocket[] = [];

/** `count` events starting at `from`, as the endpoint would hand them over. */
function pageOf(from: number, count: number) {
  return {
    events: Array.from({ length: count }, (_, n) => ({
      seq: from + n, kind: "process_completed", at_ms: 0,
      trace: { process: "STAR_ALIGN", status: "COMPLETED" },
    })),
    cursor: from + count - 1,
    stream_id: "0-0",
  };
}

function serve(pages: ReturnType<typeof pageOf>[]) {
  sockets.length = 0;
  const asked: string[] = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    asked.push(url);
    const page = pages.shift() ?? { events: [], cursor: -1, stream_id: "0-0" };
    return Promise.resolve({ ok: true, json: async () => page });
  }));
  return asked;
}

afterEach(() => vi.unstubAllGlobals());

it("keeps paging while a full page comes back", async () => {
  // The defect: it paged ONCE at limit=200 and subscribed, so a reload mid-run showed the
  // first 200 events and a silent hole. Nobody noticed because the biggest real run is five
  // tasks — the console looked complete because every run fitted in one page.
  const asked = serve([pageOf(0, 200), pageOf(200, 200), pageOf(400, 37)]);
  const { result } = renderHook(() => useRunStream("r1"));

  await waitFor(() => expect(result.current.events.length).toBe(437));
  expect(asked.filter((url) => url.includes("/events")).length).toBe(3);
});

it("subscribes once, after the record is drained and not before", async () => {
  // A socket opened after the first page would tail live events while pages 2 and 3 were
  // still arriving — which is the same hole from the other side.
  serve([pageOf(0, 200), pageOf(200, 12)]);
  const { result } = renderHook(() => useRunStream("r1"));

  await waitFor(() => expect(result.current.events.length).toBe(212));
  expect(sockets.length).toBe(1);
});

it("coalesces a burst into one state write rather than one per event", async () => {
  // A199. `setEvents((seen) => [...seen, event])` copies the whole array per message, so the
  // tail degrades quadratically as the run grows — the console gets slower the longer you
  // watch it, which is the opposite of what this slice promises.
  //
  // **Asserted on the frame count, not on the rendered length.** React batches renders on its
  // own, so "the array did not change synchronously" is true with OR without this fix and
  // proves nothing; one scheduled frame for fifty messages is only true with it.
  const frames = vi.fn();
  const realRaf = globalThis.requestAnimationFrame;
  vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) => {
    frames();
    return realRaf(fn);
  });

  serve([pageOf(0, 1)]);
  const { result } = renderHook(() => useRunStream("r1"));
  await waitFor(() => expect(result.current.events.length).toBe(1));
  frames.mockClear();

  for (let seq = 1; seq <= 50; seq += 1) {
    sockets[0].onmessage?.({ data: JSON.stringify({ seq, kind: "x", at_ms: 0 }) });
  }
  expect(frames).toHaveBeenCalledTimes(1);

  await waitFor(() => expect(result.current.events.length).toBe(51));
  const seqs = result.current.events.map((event) => event.seq);
  expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
  expect(new Set(seqs).size).toBe(51);
});
