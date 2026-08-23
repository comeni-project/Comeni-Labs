import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Compare } from "./Compare";

const rows = [
  {
    state: "same" as const,
    yours_node: "sort",
    yours_contract: "nf-core/samtools/sort@1.21.0",
    mendel_node: "sort",
    mendel_contract: "nf-core/samtools/sort@1.21.0",
    why: "",
  },
  {
    state: "differs" as const,
    yours_node: "align",
    yours_contract: "nf-core/hisat2/align@2.2.2",
    mendel_node: "align",
    mendel_contract: "nf-core/star/align@1.11.0",
    why: "rule implementation:alignment where read_length >= 70",
  },
  {
    state: "mendel-only" as const,
    yours_node: null,
    yours_contract: null,
    mendel_node: "trim",
    mendel_contract: "nf-core/trimgalore@0.6.10",
    why: "uncontested — nothing else in this registry trims",
  },
];

const noop = () => {};

describe("the compare rail", () => {
  it("says nothing has been compared rather than rendering an empty diff", () => {
    // A table with no rows reads as "you and Mendel agree", which is a claim.
    render(<Compare alignment={null} onAdopt={noop} onKeep={noop} />);
    expect(screen.getByTestId("compare-idle")).toBeInTheDocument();
    expect(screen.queryByTestId("compare-row")).toBeNull();
  });

  it("renders what Mendel would add", () => {
    render(<Compare alignment={rows} onAdopt={noop} onKeep={noop} />);
    const only = screen.getAllByTestId("compare-row").find(
      (r) => r.getAttribute("data-state") === "mendel-only",
    );
    expect(only).toHaveTextContent("trimgalore");
  });

  it("puts the differences first and the agreements last", () => {
    render(<Compare alignment={rows} onAdopt={noop} onKeep={noop} />);
    const states = screen.getAllByTestId("compare-row").map((r) => r.getAttribute("data-state"));
    expect(states.indexOf("same")).toBe(states.length - 1);
  });

  it("counts what parts company, not what exists", () => {
    render(<Compare alignment={rows} onAdopt={noop} onKeep={noop} />);
    expect(screen.getByText(/2 of 3 steps differ/)).toBeInTheDocument();
  });

  it("adopting calls the graph mutator, not the network", () => {
    const adopt = vi.fn();
    render(<Compare alignment={rows} onAdopt={adopt} onKeep={noop} />);
    fireEvent.click(screen.getAllByTestId("adopt")[0]);
    expect(adopt).toHaveBeenCalledTimes(1);
  });

  it("will not keep yours without a reason", () => {
    // An override with no reason is the defect A77 was: a person's answer replaced by
    // "selected the first of 1 candidates without judgement".
    const keep = vi.fn();
    render(<Compare alignment={rows} onAdopt={noop} onKeep={keep} />);
    fireEvent.click(screen.getAllByTestId("keep")[0]);
    expect(screen.getByTestId("keep-confirm")).toBeDisabled();
    fireEvent.change(screen.getByTestId("keep-reason"), { target: { value: "   " } });
    expect(screen.getByTestId("keep-confirm")).toBeDisabled();
    fireEvent.change(screen.getByTestId("keep-reason"), {
      target: { value: "our reads are 50bp" },
    });
    expect(screen.getByTestId("keep-confirm")).toBeEnabled();
    fireEvent.click(screen.getByTestId("keep-confirm"));
    expect(keep).toHaveBeenCalledWith(expect.anything(), "our reads are 50bp");
  });

  it("shows the resolver's own reason rather than one it invented", () => {
    render(<Compare alignment={rows} onAdopt={noop} onKeep={noop} />);
    expect(screen.getAllByTestId("compare-why")[0]).toHaveTextContent(
      /rule implementation:alignment|uncontested/,
    );
  });

  it("says so when nothing differs", () => {
    render(<Compare alignment={[rows[0]]} onAdopt={noop} onKeep={noop} />);
    expect(screen.getByText(/Identical to what Mendel resolves/)).toBeInTheDocument();
  });
});
