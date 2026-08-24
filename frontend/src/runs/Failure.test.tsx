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
