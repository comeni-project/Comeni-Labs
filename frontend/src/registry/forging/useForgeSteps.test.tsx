import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type { Step } from "./progress";
import { useForgeSteps } from "./useForgeSteps";

const step = (seq: number): Step => ({ seq, kind: "asking", data: {}, at: "2026-11-01T10:00:00Z" });

class FakeSource {
  static made: FakeSource[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  ends: (() => void)[] = [];
  url: string;
  constructor(url: string) { this.url = url; FakeSource.made.push(this); }
  addEventListener(_kind: string, listener: () => void) { this.ends.push(listener); }
  close() { this.closed = true; }
}

let record: Step[];
let reads: number;

beforeEach(() => {
  FakeSource.made = [];
  record = [step(1)];
  reads = 0;
  vi.stubGlobal("EventSource", FakeSource);
  vi.stubGlobal("fetch", vi.fn(async () => {
    reads += 1;
    return new Response(JSON.stringify(record), { status: 200, headers: { "content-type": "application/json" } });
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function follow(working: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return renderHook(({ on }) => useForgeSteps("a1", on), { wrapper, initialProps: { on: working } });
}

it("reads the record, then follows on from its last step", async () => {
  const { result } = follow(true);
  await waitFor(() => expect(FakeSource.made.length).toBe(1));
  expect(FakeSource.made[0].url).toBe("/api/forge/adaptations/a1/events/stream?after=1");
  act(() => FakeSource.made[0].onmessage?.({ data: JSON.stringify(step(2)) }));
  act(() => FakeSource.made[0].onmessage?.({ data: JSON.stringify(step(2)) }));
  await waitFor(() => expect(result.current.map((s) => s.seq)).toEqual([1, 2]));
});

it("opens no stream when nothing is working", async () => {
  const { result } = follow(false);
  await waitFor(() => expect(result.current.length).toBe(1));
  expect(FakeSource.made).toEqual([]);
});

it("falls back to reading the record when the stream drops", async () => {
  const { result } = follow(true);
  await waitFor(() => expect(FakeSource.made.length).toBe(1));
  const before = reads;
  record = [step(1), step(2)];
  act(() => FakeSource.made[0].onerror?.());
  expect(FakeSource.made[0].closed).toBe(true);
  await waitFor(() => expect(result.current.length).toBe(2), { timeout: 3_000 });
  expect(reads).toBeGreaterThan(before);
});

it("polls where the browser has no stream at all", async () => {
  vi.stubGlobal("EventSource", undefined);
  const { result } = follow(true);
  await waitFor(() => expect(result.current.length).toBe(1));
  record = [step(1), step(2)];
  await waitFor(() => expect(result.current.length).toBe(2), { timeout: 3_000 });
});
