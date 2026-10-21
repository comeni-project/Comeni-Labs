import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Panels } from "./Panels";

/** The four panels, worded as the *Run* boards word their figures. */

const TIMELINE = { lanes: [{ process: "STAR_ALIGN", declared: true, rows: 1, dense: 0,
  bars: [{ task_id: 13, attempt: 3, status: "FAILED", start_ms: 0, end_ms: 1_331_000, row: 0 }] }],
  from_ms: 0, to_ms: 1_331_000, open: false };

function panels(props: Partial<React.ComponentProps<typeof Panels>> = {}) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => TIMELINE }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Panels overview={{ steps_declared: 6, steps_finished: 2, rows: [] } as never} failed={1} retried={0}
              lastMs={null} now={0} live={false} runId="r1" {...props} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("says steps finished beside the figure", () => {
  panels();
  expect(screen.getByTestId("panel-progress")).toHaveTextContent("2 of 6 steps finished");
});

it("counts failures in tasks", () => {
  panels();
  expect(screen.getByTestId("panel-failures")).toHaveTextContent(/1\s*task/);
});

it("says how far in an ended run stopped, from the run's own span", async () => {
  panels();
  expect(await screen.findByText("22m 11s in")).toBeInTheDocument();
  expect(screen.getByTestId("panel-moving")).toHaveTextContent("ended");
});
