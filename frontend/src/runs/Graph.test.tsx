import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const STATE = {
  run_id: "4c1e9a07b2f1de40", phase: "running",
  counts: { succeeded: 12, failed: 3, cached: 0, running: 2, submitted: 0 },
  started_at_ms: 1787517649000, ended_at_ms: null,
};

const GRAPH = {
  width: 600, height: 400,
  nodes: [
    { id: "trimgalore", process: "TRIMGALORE", x: 0, y: 0, width: 232, height: 56, tier: 2,
      done: 12, failed: 0, running: 0, total: 12, attempts: 1 },
    { id: "star_align", process: "STAR_ALIGN", x: 0, y: 128, width: 232, height: 56, tier: 3,
      done: 7, failed: 3, running: 2, total: 12, attempts: 2 },
    { id: "featurecounts", process: "SUBREAD_FEATURECOUNTS", x: 0, y: 256, width: 232,
      height: 56, tier: 2, done: 0, failed: 0, running: 0, total: 0, attempts: 1 },
  ],
  wires: [
    { from_node: "trimgalore", to_node: "star_align", active: true, bytes_moved: null,
      points: [{ x: 116, y: 56 }, { x: 116, y: 128 }] },
    { from_node: "star_align", to_node: "featurecounts", active: false, bytes_moved: null,
      points: [{ x: 116, y: 184 }, { x: 116, y: 256 }] },
  ],
};

function at(graph: unknown = GRAPH) {
  vi.stubGlobal("WebSocket", class { constructor() {} close() {} });
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const body = url.includes("/graph") ? graph
      : url.includes("/events") ? { events: [], cursor: -1, stream_id: "0-0" }
        : STATE;
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  const router = createMemoryRouter(routes, {
    initialEntries: ["/runs/4c1e9a07b2f1de40?view=graph"],
  });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("draws the pipeline's own layout, coloured by what the run did", async () => {
  at();
  const star = await screen.findByTestId("node-star_align");
  expect(star).toHaveAttribute("data-state", "failed");
  expect(star).toHaveTextContent("7 / 12");
  expect(star).toHaveTextContent("3 failed");
});

it("says a step that has not been reached is waiting, not zero of zero", async () => {
  // `0 / 0` reads as a step that ran nothing successfully. A run that failed early still has a
  // whole pipeline, and the steps that never started are what tell you where it stopped.
  at();
  const last = await screen.findByTestId("node-featurecounts");
  expect(last).toHaveTextContent("waiting");
  expect(last).toHaveAttribute("data-state", "waiting");
});

it("draws a second ring when something retried, and none when nothing did", async () => {
  at();
  const retried = await screen.findByTestId("node-star_align");
  const once = await screen.findByTestId("node-trimgalore");
  expect(retried.querySelectorAll("rect")).toHaveLength(2);
  expect(once.querySelectorAll("rect")).toHaveLength(1);
});

it("animates an active edge and never implies a rate", async () => {
  // §9.2: a pulse whose speed or thickness implied MB/s would be a number nobody measured. The
  // duration is a constant, and this is the test that keeps it one.
  at();
  const active = await screen.findByTestId("wire-trimgalore-star_align");
  const animation = active.querySelector("animate");
  expect(animation).not.toBeNull();
  expect(animation!.getAttribute("dur")).toBe("0.9s");

  const still = await screen.findByTestId("wire-star_align-featurecounts");
  expect(still.querySelector("animate")).toBeNull();
});

it("switches between the two views without fetching the graph twice", async () => {
  at();
  await screen.findByTestId("run-graph");
  const graphCalls = vi.mocked(fetch).mock.calls.filter((c) => String(c[0]).includes("/graph"));
  expect(graphCalls).toHaveLength(1);
});
