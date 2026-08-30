import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const RUNS = [
  { id: "4c1e9a07b2f1de40", phase: "running", executor: "local",
    submitted_by: "operator", submitted_at: "2026-08-23T20:01:00Z",
    ended_at: null, tasks_done: 3, tasks_seen: 5, pipeline_digest: "abc" },
  { id: "77b21de4c3802f1a", phase: "failed", executor: "local",
    submitted_by: "operator", submitted_at: "2026-08-22T09:30:00Z",
    ended_at: "2026-08-22T09:31:04Z", tasks_done: 1, tasks_seen: 5,
    pipeline_digest: "abc" },
];

/** The tiles read a second endpoint, so the stub has to answer by URL now — one body for
 *  every request made the board iterate a summary as if it were a page. */
const SUMMARY = {
  window_days: 14, failed: 1, running: 1, succeeded: 6, total: 8,
  median_ms: 41_000, p95_ms: 252_000,
  // 64s — the failed run above took 64s exactly, so it is `as usual`; the running one has
  // nothing to compare against yet and gets the bare expectation.
  by_pipeline: { abc: 64_000 },
  days: Array.from({ length: 14 }, (_, n) => ({
    day: `2026-08-${String(n + 11).padStart(2, "0")}`,
    succeeded: n % 3, failed: n === 13 ? 1 : 0,
  })),
};

function at(runs: unknown = RUNS) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) =>
    Promise.resolve({
      ok: true,
      json: async () => (String(url).includes("/summary")
        ? SUMMARY
        : { runs, total: Array.isArray(runs) ? runs.length : 0 }),
    })));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs"] });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("draws a run's phase as its own colour AND as a word", async () => {
  at();
  const row = await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(row).toHaveTextContent("running");
  // The word matters as much as the hue: `failed` and `lost` share `--undecided` on purpose,
  // and a colour alone is unreadable to somebody who cannot separate the two.
  const dot = row.querySelector("[aria-hidden]") as HTMLElement;
  expect(dot.style.background).toBe("var(--measured)");
});

it("gives failed and running different colours", async () => {
  at();
  const failed = await screen.findByTestId("run-77b21de4c3802f1a");
  const dot = failed.querySelector("[aria-hidden]") as HTMLElement;
  expect(dot.style.background).toBe("var(--undecided)");
});

it("never renders a samplesheet", async () => {
  // §12: Wiener stands in the data, and §7.1 keeps it out of every table. The board could not
  // show one even if it wanted to — this is the test that keeps that true as rows gain fields.
  at();
  await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(document.body.textContent).not.toMatch(/\.csv|samplesheet|sample/i);
});

it("says what to do when there are no runs, rather than showing an empty box", async () => {
  at([]);
  await waitFor(() => expect(screen.getByText(/No runs yet/)).toBeInTheDocument());
  expect(screen.getByText(/gated/)).toBeInTheDocument();
});

it("reads the board from Wiener, not from Mendel", async () => {
  // Two APIs on one origin, split by path (vite.config.ts). A board that fetched `/api/runs`
  // from the Mendel client would 404 in dev and hit the wrong service in prod.
  at();
  await screen.findByTestId("run-4c1e9a07b2f1de40");
  // The PATH is what this is about — the query string carries paging and filters now.
  expect(String(vi.mocked(fetch).mock.calls[0][0])).toMatch(/^\/api\/runs(\?|$)/);
});

it("offers a token field when Wiener refuses, rather than a status code", async () => {
  // §12.1's check is one shared bearer token, and the board is the first Wiener page anybody
  // opens — so it is where a fresh install meets the 401. `Failed` would have printed
  // `/api/runs → 401`, which is true and tells nobody what to do about it.
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs"] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("token-prompt")).toBeTruthy());
});

it("compares a finished run against its own pipeline's usual", async () => {
  // **A median in the abstract is trivia; the same median beside a run is a judgement** —
  // `rn-board`. `by_pipeline` had been fetched since phase 2 and drawn nowhere.
  at();
  const row = await screen.findByTestId("run-77b21de4c3802f1a");
  expect(row).toHaveTextContent("as usual");
});

it("never puts a delta under a run that has not finished", async () => {
  // `-43% vs usual` under a live bar reads as *it was faster*, which is the opposite of what
  // it means: a run 43% through its usual duration has not been fast at anything yet.
  at();
  const row = await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(row).toHaveTextContent("of ~1m 04s");
  expect(row.textContent).not.toMatch(/vs usual/);
});

it("says nothing at all about a pipeline with no usual", async () => {
  // The repository refuses a median below a floor of finished runs, because *usually 38m* over
  // two runs is one number wearing the clothes of a distribution. An absent median is no
  // comparison — never a zero, and never a dash pretending to be one.
  at([{ ...RUNS[1], pipeline_digest: "never-seen-before" }]);
  await screen.findByTestId("run-77b21de4c3802f1a");
  expect(screen.queryByTestId("vs-usual")).toBeNull();
});

it("keeps the submitted-by slot and offers no filter for it", async () => {
  // **The operator's decision**: the column still says who submitted each run, because that is
  // what a reader asks of a row. What was cut is the control — on a single-operator instance
  // it offered one name and narrowed a board of 49 rows to 49.
  at();
  // Both rows carry it — `findAll`, because the slot surviving on every row is the claim.
  expect(await screen.findAllByText("operator")).toHaveLength(2);
  expect(screen.queryByLabelText("who")).toBeNull();
  expect(screen.getByLabelText("phase")).toBeInTheDocument();
});
