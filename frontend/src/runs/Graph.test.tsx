import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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
  // **The overview's words, not a fraction** — `Graph.dc.html` writes `12 done · 1 retried`,
  // and a bare `7 / 12` claims a denominator nobody can source while a run is live.
  expect(star).toHaveTextContent("7 done");
  expect(star).toHaveTextContent("3 failed");
});

it("says a step that has not been reached is waiting, not zero of zero", async () => {
  // `0 / 0` reads as a step that ran nothing successfully. A run that failed early still has a
  // whole pipeline, and the steps that never started are what tell you where it stopped.
  at();
  const last = await screen.findByTestId("node-featurecounts");
  // `not started` is the artboard's wording; `data-state` keeps the machine-readable name.
  expect(last).toHaveTextContent("not started");
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
  // The motion is `.live` in the stylesheet now — one definition shared with the artboards
  // rather than an `<animate>` per edge — but the property under test is unchanged: the
  // duration is a CONSTANT in CSS, so there is nowhere for a byte count to reach it.
  const active = await screen.findByTestId("wire-trimgalore-star_align");
  expect(active.getAttribute("class")).toContain("live");
  expect(active).toHaveAttribute("data-active", "true");

  const still = await screen.findByTestId("wire-star_align-featurecounts");
  expect(still.getAttribute("class") ?? "").not.toContain("live");
});

it("switches between the two views without fetching the graph twice", async () => {
  at();
  await screen.findByTestId("run-graph");
  const graphCalls = vi.mocked(fetch).mock.calls.filter((c) => String(c[0]).includes("/graph"));
  expect(graphCalls).toHaveLength(1);
});

it("does not put the context menu inside the transformed stage", async () => {
  // **A `position: fixed` element inside a `transform`ed ancestor is positioned against that
  // ancestor, not the viewport.** `Canvas` renders its children inside a stage carrying
  // `translate(...) scale(...)`, so a menu placed there drifts further from the cursor the
  // further you have panned — and it drifts by exactly the pan, which reads as "the menu
  // spawns a long way off" rather than as a CSS rule.
  //
  // jsdom does no layout, so the offset itself cannot be measured here. The STRUCTURE can:
  // the menu must not be a descendant of the stage. That is the property the fix restores and
  // the one a later tidy-up would undo.
  at();
  const node = await screen.findByTestId("node-star_align");
  fireEvent.contextMenu(node, { clientX: 120, clientY: 90 });

  const menu = await screen.findByRole("menu");
  const stage = screen.getByTestId("stage");
  expect(stage.contains(menu)).toBe(false);
});
