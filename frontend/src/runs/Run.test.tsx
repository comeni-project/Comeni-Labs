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

const OVERVIEW = {
  rows: [{
    process: "TRIMGALORE", declared: true, reached: true,
    tasks: 1, done: 1, running: 0, failed: 0, cached: 0, attempts_max: 1,
    memory_asked_bytes: 1073741824, memory_peak_bytes: 8785920,
    cpus_asked: 6, cpu_used_pct: 202.4,
    realtime_ms: 343, queue_wait_ms: 617, read_bytes: 0, write_bytes: 0,
  }],
  steps_declared: 1, steps_finished: 1,
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

/** `view` is a parameter now, because the console is no longer what the page opens on — W2
 *  Task 6. A test about the socket has to say so rather than relying on the landing view. */
function at(state: unknown = STATE, page: unknown = PAGE, view = "console",
            overview: unknown = OVERVIEW) {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const body = url.includes("/events") ? page
      : url.includes("/overview") ? overview
      : state;
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  const router = createMemoryRouter(routes, {
    initialEntries: [`/runs/4c1e9a07b2f1de40?view=${view}`],
  });
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

it("opens on the overview, not the console", async () => {
  // **W2's ending condition, as a test.** §18: you can read a 400-task run without reading
  // text — which is a statement that the console cannot be what the page opens on. It keeps
  // its shape and becomes a tab. This test asserted the opposite until 2026-08-24.
  at(STATE, PAGE, "overview");
  expect(await screen.findByRole("button", { name: "Overview" }))
    .toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Console" }))
    .toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: "Graph" }))
    .toHaveAttribute("aria-pressed", "false");
});

it("draws the Tasks tab disabled rather than hiding it", async () => {
  // The same call this page already made about `Graph` between phases 2 and 3: a control that
  // goes nowhere SILENTLY is the mistake `Shell.tsx` records 3A shipping six of. Drawn and
  // disabled says the run has a tasks view and it is not built; hidden says nothing.
  at(STATE, PAGE, "overview");
  expect(await screen.findByRole("button", { name: "Tasks" })).toBeDisabled();
});


it("draws progress over steps the artifact declared, never over tasks seen", async () => {
  // §5. Nextflow discovers tasks as channels emit, so a task denominator GROWS and a
  // percentage over it goes backwards. The artifact's step count is known at t=0.
  at(STATE, PAGE, "overview", {
    steps_declared: 5, steps_finished: 3,
    rows: [{ ...OVERVIEW.rows[0], tasks: 28, done: 8, running: 20 }],
  });
  const bar = await screen.findByTestId("run-progress");
  expect(bar).toHaveTextContent("3 of 5 steps finished");
  expect(bar).not.toHaveTextContent("28");
});

it("says nothing about steps when the artifact could not be read", async () => {
  // A192's other half, drawn. `steps_declared: 0` means the directory is gone, and a bar
  // over a denominator of zero would be an invented number where there is no fact.
  at(STATE, PAGE, "overview", { steps_declared: 0, steps_finished: 0, rows: OVERVIEW.rows });
  await screen.findByTestId("row-TRIMGALORE");
  expect(screen.queryByTestId("run-progress")).toBeNull();
});
