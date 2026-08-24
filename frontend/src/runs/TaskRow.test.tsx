import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { TaskRow, type TaskView } from "./TaskRow";

const BASE: TaskView = {
  task_id: 3, process: "STAR_ALIGN", tag: "sample_07", status: "COMPLETED",
  attempts: 1, latest_exit: 0,
  peak_rss_bytes: 1_273_368_576, pct_cpu: 100.2, realtime_ms: 31_670,
};

it("marks a retry without making you count attempts", () => {
  render(<TaskRow task={{ ...BASE, attempts: 2 }} showProcess={false} />);
  expect(screen.getByTestId("retried")).toHaveTextContent("2");
});

it("shows an absent measurement as a dash, never as zero", () => {
  render(<TaskRow task={{ ...BASE, peak_rss_bytes: null }} showProcess={false} />);
  expect(screen.getByTestId("mem")).toHaveTextContent("—");
  expect(screen.getByTestId("mem")).not.toHaveTextContent("0");
});

it("identifies a task by its id when the run predates the labels column", () => {
  // A200: `labels` was added on 2026-08-24 and nothing back-fills it, so a run ingested
  // before it has no tag at all. The row must still say WHICH task it is.
  render(<TaskRow task={{ ...BASE, tag: null }} showProcess={false} />);
  expect(screen.getByTestId("task")).toHaveTextContent("3");
});

it("names an out-of-memory kill rather than printing 137", () => {
  // 137 is SIGKILL and on a Nextflow task it is nearly always the OOM killer. A reader who
  // has to look that up is a reader the interface failed.
  render(<TaskRow task={{ ...BASE, latest_exit: 137, status: "FAILED" }} showProcess={false} />);
  expect(screen.getByTestId("mark")).toHaveTextContent(/out of memory/i);
});

it("adds a process column only for the tab that spans processes", () => {
  const { rerender } = render(<TaskRow task={BASE} showProcess={false} />);
  expect(screen.queryByTestId("process")).toBeNull();
  rerender(<TaskRow task={BASE} showProcess />);
  expect(screen.getByTestId("process")).toHaveTextContent("STAR_ALIGN");
});
