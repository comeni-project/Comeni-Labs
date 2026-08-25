import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Overview, OverviewPanel, type OverviewData, type Row } from "./Overview";

const ROW: Row = {
  process: "STAR_ALIGN", declared: true, reached: true,
  tasks: 1, done: 1, running: 0, failed: 0, cached: 0, attempts_max: 1,
  memory_asked_bytes: 34_359_738_368, memory_peak_bytes: 1_273_368_576,
  cpus_asked: 12, cpu_used_pct: 100.2,
  realtime_ms: 31_670, queue_wait_ms: 704,
  read_bytes: 53_248, write_bytes: 1_000,
};
const OK: OverviewData = { rows: [ROW], steps_declared: 1, steps_finished: 1 };

const NOT_STARTED: Row = {
  ...ROW, process: "MULTIQC", reached: false,
  tasks: 0, done: 0, attempts_max: 1,
  memory_asked_bytes: null, memory_peak_bytes: null, cpus_asked: null, cpu_used_pct: null,
  realtime_ms: null, queue_wait_ms: null, read_bytes: null, write_bytes: null,
};
const SLOW: Row = { ...ROW, process: "SLOW", realtime_ms: 60_000 };
const FAST: Row = { ...ROW, process: "FAST", realtime_ms: 1_000 };
const NO_TRACE: Row = { ...ROW, memory_peak_bytes: null, cpu_used_pct: null };
const LIVE: Row = { ...ROW, process: "FEATURECOUNTS", tasks: 12, done: 3, running: 9 };

it("gives a declared process a row before the run reaches it", () => {
  render(<Overview data={{ ...OK, rows: [NOT_STARTED] }} />);
  expect(screen.getByTestId("row-MULTIQC")).toHaveTextContent("not started");
});

it("scales every bar in a column against the same maximum", () => {
  // A small multiple is only a comparison if the axes agree. Two bars scaled to their own
  // row say nothing about each other, which is the entire point of putting them in a column.
  render(<Overview data={{ ...OK, rows: [SLOW, FAST] }} />);
  // **Addressed per row.** This read `getAllByTestId("bar-time")` and took [0] and [1], which
  // worked only because every row rendered the same bare `bar-time` — the one bar in the table
  // whose testid was not suffixed with its process. Two rows, one id: the test passed on an
  // ambiguity, and nothing could have addressed a single row's realtime bar.
  const slow = screen.getByTestId("bar-time-SLOW");
  const fast = screen.getByTestId("bar-time-FAST");
  expect(parseFloat(slow.style.width)).toBeGreaterThan(parseFloat(fast.style.width) * 5);
});

it("renders an absent measurement as a dash and never as zero", () => {
  render(<Overview data={{ ...OK, rows: [NO_TRACE] }} />);
  expect(screen.getByTestId("mem-STAR_ALIGN")).toHaveTextContent("—");
  expect(screen.getByTestId("mem-STAR_ALIGN")).not.toHaveTextContent("0%");
});

it("claims no total while a process is live", () => {
  render(<Overview data={{ ...OK, rows: [LIVE] }} />);
  expect(screen.getByTestId("count-FEATURECOUNTS")).toHaveTextContent("3 done");
  expect(screen.getByTestId("count-FEATURECOUNTS")).toHaveTextContent("9 more seen");
  expect(screen.getByTestId("count-FEATURECOUNTS")).not.toHaveTextContent("3 / 12");
});

it("puts retries on the row rather than behind an expand", () => {
  render(<Overview data={{ ...OK, rows: [{ ...ROW, attempts_max: 3 }] }} />);
  expect(screen.getByTestId("row-STAR_ALIGN")).toHaveTextContent("↻");
});


const TASKS = {
  tasks: [
    { task_id: 2, process: "STAR_ALIGN", status: "COMPLETED", tag: "sample_07",
      attempts: 2, latest_exit: 0, last_change_ms: 0,
      peak_rss_bytes: 1_273_368_576, realtime_ms: 31_670, pct_cpu: 100.2 },
  ],
  total: 1,
};

function panel(overview: unknown = OK, tasks: unknown = TASKS) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    calls.push(url);
    return Promise.resolve({
      ok: true,
      json: async () => (url.includes("/tasks") ? tasks : overview),
    });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <OverviewPanel runId="r1" />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("fetches a process's tasks only once you ask for them", async () => {
  // `enabled` while expanded, and not before. A run with forty processes must not open forty
  // queries to draw a table nobody has clicked yet.
  const calls = panel();
  await screen.findByTestId("row-STAR_ALIGN");
  expect(calls.some((url) => url.includes("/tasks"))).toBe(false);

  await userEvent.click(screen.getByTestId("expand-STAR_ALIGN"));
  await waitFor(() => expect(calls.some((url) =>
    url.includes("/tasks") && url.includes("process=STAR_ALIGN"))).toBe(true));
  expect(await screen.findByTestId("task-2")).toHaveTextContent("sample_07");
});

it("collapses again, and the caret says which way it is", async () => {
  panel();
  const caret = await screen.findByTestId("expand-STAR_ALIGN");
  expect(caret).toHaveAttribute("aria-expanded", "false");

  await userEvent.click(caret);
  expect(await screen.findByTestId("task-2")).toBeInTheDocument();
  expect(caret).toHaveAttribute("aria-expanded", "true");

  await userEvent.click(caret);
  await waitFor(() => expect(screen.queryByTestId("task-2")).toBeNull());
  expect(caret).toHaveAttribute("aria-expanded", "false");
});
