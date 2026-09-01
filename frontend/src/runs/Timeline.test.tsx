import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Timeline } from "./Timeline";

/** The renderer's half of the rules. **The deciding half is `wiener_core.timeline`** and is
 *  tested there — these assert only what a component can get wrong: extending an open bar,
 *  drawing a lane that has nothing, and hiding a density band. */

function at(body: unknown, live = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => body }));
  return render(
    <QueryClientProvider client={makeClient()}>
      <Timeline runId="r1" live={live} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const LANE = {
  process: "STAR_ALIGN", declared: true, rows: 1, dense: 0,
  bars: [{ task_id: 3, attempt: 1, status: "COMPLETED", start_ms: 0, end_ms: 60_000, row: 0 }],
};

it("draws a bar per attempt, named by the task it belongs to", async () => {
  at({ lanes: [LANE], from_ms: 0, to_ms: 60_000, open: false });
  expect(await screen.findByTestId("bar-3-1")).toBeInTheDocument();
});

it("extends a running bar to the right edge rather than drawing it as zero-length", async () => {
  // **The one rule that is the renderer's**, because the verb cannot keep it: `now` inside a
  // pure fold makes the same events draw differently every second, so `wiener-core` sends
  // `end_ms: null` and this decides where the edge is. A zero-width bar would say a task
  // started and stopped instantly, which is the opposite of *it is still going*.
  at({
    lanes: [{ ...LANE, bars: [{ ...LANE.bars[0], end_ms: null, status: "RUNNING" }] }],
    from_ms: 0, to_ms: 60_000, open: true,
  });
  const bar = await screen.findByTestId("bar-3-1");
  expect(Number(bar.getAttribute("width"))).toBeGreaterThan(1);
});

it("says how many bars would not fit rather than dropping them quietly", async () => {
  // A chart that omits 4,960 bars without saying so is a chart that lies about a run.
  at({
    lanes: [{ ...LANE, dense: 4960 }],
    from_ms: 0, to_ms: 60_000, open: false,
  });
  expect(await screen.findByTestId("dense-STAR_ALIGN")).toHaveTextContent("4960");
});

it("draws nothing at all rather than an empty frame when no attempt has run", async () => {
  // **Absence is absence** — the rule `Envelope` already keeps. An empty chart with axes claims
  // a run that did nothing; the page is simply shorter.
  const { container } = at({
    lanes: [{ process: "STAR_ALIGN", declared: true, rows: 0, dense: 0, bars: [] }],
    from_ms: 0, to_ms: 0, open: false,
  });
  expect(container.querySelector("[data-testid='band-timeline']")).toBeNull();
});

it("reports the lane somebody clicked, so the table below can filter in place", async () => {
  // *"Drill down IN PLACE. Clicking a timeline lane filters the tasks table below it. Never a
  // second page for the same run."* The band knows nothing about the table — it reports which
  // lane was picked and the page decides what that means, which is why this asserts a callback
  // rather than a rendered consequence.
  const picked: string[] = [];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ lanes: [LANE], from_ms: 0, to_ms: 60_000, open: false }),
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Timeline runId="r1" live={false} onPickLane={(p) => picked.push(p)} />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByTestId("lane-STAR_ALIGN"));
  expect(picked).toEqual(["STAR_ALIGN"]);
});

it("does not offer a lane with nothing in it as something to click", async () => {
  // An empty lane filters the table to nothing, which reads as *this process has no tasks*
  // when the truth is *it has not started*. `overview()` answers that question and says so.
  const picked: string[] = [];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      lanes: [LANE, { process: "MULTIQC", declared: true, rows: 0, dense: 0, bars: [] }],
      from_ms: 0, to_ms: 60_000, open: false,
    }),
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Timeline runId="r1" live={false} onPickLane={(p) => picked.push(p)} />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByTestId("lane-MULTIQC"));
  expect(picked).toEqual([]);
});
