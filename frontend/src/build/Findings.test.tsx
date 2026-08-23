import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Findings } from "./Findings";

const findings = [
  {
    code: "MD0507",
    level: "advisory" as const,
    message: "MD0507: align.reads conventionally wants ['trimmed']",
    node: null,
    port: null,
    source: "trim.reads",
    target: "align.reads",
  },
  {
    code: "MD0504",
    level: "illegal" as const,
    message: "MD0504: counts.bam requires ['coordinate_sorted']; align.bam carries []",
    node: null,
    port: null,
    source: "align.bam",
    target: "counts.bam",
  },
  {
    code: "MD0506",
    level: "unmet" as const,
    message: "MD0506: align.index has no wire and its type declares no entry channel",
    node: "align",
    port: "index",
    source: null,
    target: null,
  },
];

describe("the findings list", () => {
  it("says the graph is clean rather than rendering nothing", () => {
    render(<Findings findings={[]} onSelect={() => {}} />);
    expect(screen.getByTestId("findings-clear")).toBeInTheDocument();
  });

  it("puts illegal first and advisory last", () => {
    render(<Findings findings={findings} onSelect={() => {}} />);
    const levels = screen.getAllByTestId("finding").map((f) => f.getAttribute("data-level"));
    expect(levels).toEqual(["illegal", "unmet", "advisory"]);
  });

  it("shows every code, so a runbook can cite one", () => {
    render(<Findings findings={findings} onSelect={() => {}} />);
    for (const code of ["MD0504", "MD0506", "MD0507"]) {
      expect(screen.getByText(code)).toBeInTheDocument();
    }
  });

  it("does not print the code twice", () => {
    // `coded()` already puts it on the front of the message. Rendering both would be two
    // spellings of one string.
    render(<Findings findings={[findings[1]]} onSelect={() => {}} />);
    expect(screen.getByTestId("finding").textContent?.match(/MD0504/g)).toHaveLength(1);
  });

  it("selects the node a finding is about", () => {
    const select = vi.fn();
    render(<Findings findings={[findings[2]]} onSelect={select} />);
    fireEvent.click(screen.getByRole("button"));
    expect(select).toHaveBeenCalledWith("align");
  });

  it("selects the consuming node when the finding is about a wire", () => {
    // A finding names two endpoints as `<node>.<port>`. The one worth navigating to is the
    // consumer: that is where the fix goes.
    const select = vi.fn();
    render(<Findings findings={[findings[1]]} onSelect={select} />);
    fireEvent.click(screen.getByRole("button"));
    expect(select).toHaveBeenCalledWith("counts");
  });
});
