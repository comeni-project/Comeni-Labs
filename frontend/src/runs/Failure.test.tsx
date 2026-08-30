import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { Failure, type Failed } from "./Failure";

const FAILED: Failed = {
  process: "STAR_ALIGN", tag: "sample_07", exit: 137, attempts: 2,
  peak_rss_bytes: 68_500_000_000, asked_bytes: 68_719_476_736,
  report: "Process `STAR_ALIGN (sample_07)` terminated with an error exit status (137)\n"
    + "Command error: an oom-kill event was detected",
};

it("names the task, the code and the attempt, from the record", () => {
  render(<Failure failed={FAILED} />);
  expect(screen.getByTestId("failure")).toHaveTextContent("STAR_ALIGN");
  expect(screen.getByTestId("failure")).toHaveTextContent("137");
  expect(screen.getByTestId("failure")).toHaveTextContent("attempt 2");
});

it("shows the resource line only when both halves are known", () => {
  // Half a comparison is worse than none: '63.8 GB' with nothing to compare it against
  // invites the reader to supply a ceiling they do not have.
  render(<Failure failed={{ ...FAILED, asked_bytes: null }} />);
  expect(screen.queryByTestId("failure-resources")).toBeNull();

  render(<Failure failed={FAILED} />);
  expect(screen.getByTestId("failure-resources")).toHaveTextContent("of");
});

it("renders Nextflow's own report and interprets nothing", () => {
  render(<Failure failed={FAILED} />);
  expect(screen.getByTestId("failure-report")).toHaveTextContent("oom-kill event");
});

it("says what it can when the record carries no report", () => {
  // §18.1: nothing EXPLAINS a failure until W3. A banner that invented a cause here would be
  // the shortfall pretending to be a feature.
  render(<Failure failed={{ ...FAILED, report: null }} />);
  expect(screen.getByTestId("failure")).toHaveTextContent("STAR_ALIGN");
  expect(screen.queryByTestId("failure-report")).toBeNull();
});

it("says the run failed even when no task did", () => {
  // A run can stop before any task starts — a bad parameter, a file the channel could not
  // read. The phase is `failed`, there is no failed task, and the record still carries
  // Nextflow's report. A banner that rendered NOTHING here would leave a failed run with no
  // account of itself, which is the one thing this banner exists to prevent.
  render(<Failure failed={{ ...FAILED, process: null, exit: null }} />);
  expect(screen.getByTestId("failure")).toHaveTextContent(/no task failed/i);
  expect(screen.getByTestId("failure-report")).toHaveTextContent("oom-kill event");
});

const ESCALATION = [
  { n: 1, status: "FAILED", exit: 137, signal: "SIGKILL",
    memory_bytes: 38_654_705_664, peak_rss_bytes: 38_400_000_000, realtime_ms: 1_000 },
  { n: 2, status: "FAILED", exit: 137, signal: "SIGKILL",
    memory_bytes: 51_539_607_552, peak_rss_bytes: 51_200_000_000, realtime_ms: 2_000 },
  { n: 3, status: "COMPLETED", exit: 0, signal: null,
    memory_bytes: 77_309_411_328, peak_rss_bytes: 65_700_000_000, realtime_ms: 3_000 },
];

it("shows what each attempt asked for beside what it touched", () => {
  // **The story `attempts: 3` cannot tell.** 36 → 48 → 72 GB is the whole reason retries are
  // kept as history (§5.1), and it sat in a JSON column that nothing projected until phase 4.
  render(<Failure failed={{ ...FAILED, attempts: 3, history: ESCALATION }} />);

  // `asked 36 GB · touched 36 GB` — and the two reading the SAME is the story, not a rounding
  // bug: a task that touched its entire reservation is a task that died of it. `bytes()` rounds
  // 35.76 GiB to `36 GB` by the spelling rule the whole product shares, and forcing an extra
  // digit here to make the halves look different would be making them disagree on purpose.
  expect(screen.getByTestId("attempt-1")).toHaveTextContent("asked 36 GB · touched 36 GB");
  // The last try is the one with room to spare, which is why it is the one that finished.
  expect(screen.getByTestId("attempt-3")).toHaveTextContent("asked 72 GB · touched 61 GB");
});

it("shows the signal gloss as given and authors no cause of its own", () => {
  // §18.1. `137` is `SIGKILL` — the 128+n convention, arithmetic. *The OOM killer did it* is
  // an inference a preemption and a `kill -9` share, and nothing explains a failure until W3.
  //
  // **The record is excluded from the scan, and that exclusion is the whole point.** Nextflow's
  // own errorReport says `an oom-kill event was detected` and this panel shows it verbatim —
  // quoting the record is what the banner is FOR. What it must never do is author that sentence
  // itself. A scan over the whole banner would have forced the panel to censor the record to
  // stay green, which is the opposite of the rule it is enforcing.
  render(<Failure failed={{ ...FAILED, attempts: 3, history: ESCALATION }} />);

  expect(screen.getByTestId("attempt-1")).toHaveTextContent("exit 137 · SIGKILL");

  const banner = screen.getByTestId("failure").cloneNode(true) as HTMLElement;
  banner.querySelector('[data-testid="failure-report"]')?.remove();
  const words = ["oom", "out of memory", "ran out", "killed by", "caused by",
                 "try increasing", "you should", "probably"];
  for (const word of words) {
    expect(banner.textContent?.toLowerCase()).not.toContain(word);
  }
});

it("draws no escalation for a task that only tried once", () => {
  // Absence is absence. One try has nothing to escalate, and its asked-beside-touched is
  // already the bar above — a one-row "escalation" would be a heading over a single fact.
  render(<Failure failed={{
    ...FAILED, attempts: 1,
    history: [{ n: 1, status: "FAILED", exit: 1, signal: null,
                memory_bytes: 38_654_705_664, peak_rss_bytes: 1_000, realtime_ms: 1 }],
  }} />);

  expect(screen.queryByTestId("failure-escalation")).toBeNull();
  // The reservation is still on screen, which is this row's only place for it.
  expect(screen.getByTestId("failure-resources")).toBeInTheDocument();
});

it("survives a record that predates the projection", () => {
  // Every run in the database before 2026-08-30 has no `history`. The banner keeps its shape.
  render(<Failure failed={FAILED} />);
  expect(screen.queryByTestId("failure-escalation")).toBeNull();
  expect(screen.getByTestId("failure")).toBeInTheDocument();
});
