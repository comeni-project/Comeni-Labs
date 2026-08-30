import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Envelope } from "./Envelope";

const EXACT = {
  name: "cpu reserved", kind: "exact", unit: "cpus",
  points: [{ at_ms: 0, value: 4 }, { at_ms: 100, value: 12 }, { at_ms: 300, value: 4 }],
};
const DERIVED = {
  name: "read", kind: "derived", unit: "bytes/s",
  points: [{ at_ms: 0, value: 500 }, { at_ms: 200, value: 0 }],
};

function series(over: Record<string, unknown> = {}) {
  return {
    curves: [EXACT, DERIVED], from_ms: 0, to_ms: 400, bin_ms: 3,
    open: false, reported_resources: true, ...over,
  };
}

function at(body: unknown = series()) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() =>
    Promise.resolve({ ok: true, json: async () => body })));
  return render(
    <QueryClientProvider client={makeClient()}>
      <Envelope runId="r1" live={false} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("never draws a derived curve smooth", async () => {
  // **The rule phase 5 exists to enforce, asserted where it can actually be lost.** `curve.ts`
  // holds the path builder; this holds the component that could still have reached for a chart
  // library. A `derived` curve is area-true and shape-false, and a spline is a picture of
  // measurements nobody took.
  at();
  const drawn = await screen.findByTestId("curve-read");

  const path = drawn.getAttribute("data-path") ?? "";
  expect(path).not.toMatch(/[CcSsQqTtAa]/);
  expect(path.length).toBeGreaterThan(0);
});

it("says derived on the curve and not only in a legend", async () => {
  // A screenshot with the legend cropped off is the common way this page is shared.
  at();
  expect(await screen.findByText("derived")).toBeInTheDocument();

  const exact = await screen.findByTestId("curve-cpu-reserved");
  expect(exact).toHaveAttribute("data-kind", "exact");
});

it("draws no memory-over-time curve, because the API offers none", async () => {
  // The absence travels all the way to the pixel. `wiener_core.series` has no third `Kind`,
  // the route adds nothing, and this component cannot invent one — summing peaks across live
  // attempts describes an instant that never happened.
  at();
  await screen.findByTestId("curve-read");
  expect(screen.queryByText(/peak rss|memory used|memory over time/i)).toBeNull();
});

it("says the right edge is not an ending while work is in flight", async () => {
  // A curve ending high because tasks are running reads identically to one ending high because
  // the run stopped badly. Only `open` distinguishes them.
  at(series({ open: true }));
  expect(await screen.findByText(/still in flight/)).toBeInTheDocument();
});

it("answers a run without trace with a sentence rather than empty charts", async () => {
  at(series({
    reported_resources: false,
    curves: [{ name: "attempts in flight", kind: "exact", unit: "tasks",
               points: [{ at_ms: 0, value: 1 }] }],
  }));

  expect(await screen.findByText(/reported no resource figures/)).toBeInTheDocument();
  // **Absent is not zero.** The countable curve is still exact and still honest, so it stays.
  expect(screen.getByTestId("curve-attempts-in-flight")).toBeInTheDocument();
  expect(screen.queryByTestId("curve-cpu-reserved")).toBeNull();
});

it("renders nothing at all when the record is empty", async () => {
  // Absence is absence: a run that recorded nothing gets no panel, not an empty one.
  const { container } = at(series({ curves: [], reported_resources: false }));
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
