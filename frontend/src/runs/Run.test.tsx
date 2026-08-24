import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const STATE = {
  run_id: "4c1e9a07b2f1de40", phase: "running",
  counts: { succeeded: 2, failed: 0, cached: 0, running: 1, submitted: 0 },
  started_at_ms: 1787517649000, ended_at_ms: null,
};

const PAGE = {
  events: [
    { seq: 0, kind: "started", at_ms: 1787517649000 },
    { seq: 1, kind: "process_completed", at_ms: 1787517650000,
      trace: { process: "TRIMGALORE", status: "COMPLETED", name: "TRIMGALORE (test)",
               realtime_ms: 643 } },
  ],
  cursor: 1,
  stream_id: "1787517650000-0",
};

/** Every socket the page opens, so a test can assert what it was asked for and push to it. */
const sockets: FakeSocket[] = [];

class FakeSocket {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    sockets.push(this);
    queueMicrotask(() => this.onopen?.());
  }
  close() {
    this.closed = true;
  }
}

function at(state: unknown = STATE, page: unknown = PAGE) {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const body = url.includes("/events") ? page : state;
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs/4c1e9a07b2f1de40"] });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("pages the record before it subscribes, and subscribes from where the page ended", async () => {
  at();
  await screen.findByTestId("console");
  await waitFor(() => expect(sockets).toHaveLength(1));
  // **The whole of §7.2 in one assertion.** Subscribing from zero replays what the page just
  // drew; subscribing from `$` drops whatever arrived between the two requests.
  expect(sockets[0].url).toContain(`from=${encodeURIComponent(PAGE.stream_id)}`);
});

it("draws the paged events before anything arrives on the socket", async () => {
  at();
  expect(await screen.findByTestId("event-1")).toHaveTextContent("TRIMGALORE");
});

it("appends what the socket sends without redrawing what it already has", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));

  sockets[0].onmessage?.({ data: JSON.stringify({
    seq: 2, kind: "process_completed", at_ms: 1787517651000,
    trace: { process: "STAR_ALIGN", status: "COMPLETED", name: "STAR_ALIGN (test)",
             realtime_ms: 29423 } }) });
  expect(await screen.findByTestId("event-2")).toHaveTextContent("STAR_ALIGN");

  // The same event again — a reconnect can redeliver — must not draw a second row.
  sockets[0].onmessage?.({ data: JSON.stringify({
    seq: 2, kind: "process_completed", at_ms: 1787517651000,
    trace: { process: "STAR_ALIGN", status: "COMPLETED", name: "STAR_ALIGN (test)",
             realtime_ms: 29423 } }) });
  expect(screen.getAllByTestId("event-2")).toHaveLength(1);
});

it("does not reopen a socket for a run the server says is over", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));
  sockets[0].onclose?.({ code: 1000 });   // drained and terminal
  await new Promise((r) => setTimeout(r, 20));
  expect(sockets).toHaveLength(1);
});

it("re-pages when the connection drops, rather than reopening blind", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));
  sockets[0].onclose?.({ code: 1006 });   // the connection went away
  await waitFor(() => expect(sockets).toHaveLength(2));
  const paged = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
  expect(paged.filter((u) => u.includes("/events")).length).toBeGreaterThan(1);
});

it("says it is read-only rather than pretending it is not", async () => {
  at();
  expect(await screen.findByText(/read-only until W4/i)).toBeInTheDocument();
});

it("draws the Graph segment as disabled rather than omitting it", async () => {
  // A control that goes nowhere SILENTLY is what Shell.tsx records as the mistake 3A shipped
  // six of. Phase 3 builds the graph; until then it says so.
  at();
  const graph = await screen.findByTitle(/graph view is phase 3/i);
  expect(graph).toHaveAttribute("aria-disabled", "true");
});
