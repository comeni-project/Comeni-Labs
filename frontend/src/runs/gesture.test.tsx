import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** **A menu on one page and nowhere else is worse than none**, because it teaches a gesture
 * that then fails — §12.3. This is the test for the "everywhere" half: it right-clicks each
 * surface that offers the gesture and requires a menu.
 */
const STATE = {
  run_id: "4c1e9a07b2f1de40", phase: "running",
  counts: { succeeded: 2, failed: 0, cached: 0, running: 1, submitted: 0 },
  started_at_ms: 1787517649000, ended_at_ms: null,
};
const OVERVIEW = {
  rows: [{
    process: "STAR_ALIGN", declared: true, reached: true,
    tasks: 1, done: 1, running: 0, failed: 0, cached: 0, attempts_max: 1,
    memory_asked_bytes: 100, memory_peak_bytes: 50, cpus_asked: 2, cpu_used_pct: 90,
    realtime_ms: 10, queue_wait_ms: 1, read_bytes: 1, write_bytes: 1,
  }],
  steps_declared: 1, steps_finished: 1,
};
const EVENTS = {
  events: [{ seq: 0, kind: "process_completed", at_ms: 1787517650000,
             trace: { process: "STAR_ALIGN", status: "COMPLETED", name: "STAR_ALIGN (s1)" } }],
  cursor: 0, stream_id: "0-0",
};
const RUNS = [{ id: "4c1e9a07b2f1de40", phase: "running", executor: "local",
                submitted_by: "operator", submitted_at: "2026-08-23T20:01:00Z" }];
const GRAPH = {
  nodes: [{ id: "star_align", label: "STAR_ALIGN", x: 10, y: 10, width: 100, height: 40,
            total: 1, done: 1, failed: 0, running: 0, attempts: 1 }],
  wires: [], width: 200, height: 200,
};
const TASKS = { total: 1, tasks: [{ task_id: 1, process: "STAR_ALIGN", status: "COMPLETED",
                tag: "s1", attempts: 1, latest_exit: 0, last_change_ms: 0,
                peak_rss_bytes: 5, realtime_ms: 5, pct_cpu: 50 }] };

class FakeSocket {
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor() { queueMicrotask(() => this.onopen?.()); }
  close() {}
}

function at(path: string) {
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) =>
    Promise.resolve({
      ok: true,
      json: async () =>
        url.includes("/events") ? EVENTS
        : url.includes("/overview") ? OVERVIEW
        : url.includes("/graph") ? GRAPH
        : url.includes("/tasks") ? TASKS
        : url.endsWith("/api/runs") ? RUNS
        : STATE,
    })));
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.getSelection()?.removeAllRanges();
});

const SURFACES = [
  { what: "a board row", path: "/runs", testId: "run-4c1e9a07b2f1de40" },
  { what: "a process row", path: "/runs/4c1e9a07b2f1de40?view=overview", testId: "row-STAR_ALIGN" },
  { what: "a console line", path: "/runs/4c1e9a07b2f1de40?view=console", testId: "event-0" },
  { what: "a graph node", path: "/runs/4c1e9a07b2f1de40?view=graph", testId: "node-star_align" },
  { what: "a task row", path: "/runs/4c1e9a07b2f1de40?view=tasks", testId: "task-1" },
];

describe("the right-click gesture", () => {
  it.each(SURFACES)("answers on $what", async ({ testId }) => {
    at(SURFACES.find((s) => s.testId === testId)!.path);
    const surface = await screen.findByTestId(testId);
    fireEvent.contextMenu(surface);
    await waitFor(() => expect(screen.getByTestId("menu")).toBeTruthy());
  });
});
