import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Samples } from "./Samples";

const sample = (name: string, paired: boolean, length: number) => ({
  name, files: [`${name}_R1.fq.gz`], outcome: "measured",
  facts: [{ measurement: "paired", value: paired, coverage: "head" as const },
          { measurement: "read_length", value: length, coverage: "head" as const }],
});

describe("the samples of an upload (issue 466)", () => {
  it("lists every sample with each measurement", () => {
    render(<Samples samples={[sample("a", true, 150), sample("b", false, 75)]} />);
    const rows = screen.getAllByTestId("sample-row");
    expect(rows.map((r) => r.textContent)).toEqual(["atrue150", "bfalse75"]);
  });

  it("groups by a measurement, with counts", async () => {
    render(<Samples samples={[sample("a", true, 150), sample("b", true, 150), sample("c", false, 75)]} />);
    await userEvent.selectOptions(screen.getByLabelText("group samples by"), "paired");
    expect(screen.getAllByTestId("sample-group").map((g) => g.textContent)).toEqual(
      ["true: 2", "false: 1"]);
  });

  it("filters by name and pages hundreds of samples", async () => {
    const many = Array.from({ length: 500 }, (_, n) => sample(`s${String(n).padStart(3, "0")}`, true, 150));
    render(<Samples samples={many} />);
    expect(screen.getAllByTestId("sample-row")).toHaveLength(50);
    expect(screen.getByText("page 1 of 10")).toBeTruthy();
    await userEvent.type(screen.getByLabelText("filter samples by name"), "s49");
    expect(screen.getAllByTestId("sample-row")).toHaveLength(10);
    expect(within(screen.getAllByTestId("sample-row")[0]).getByText("s490")).toBeTruthy();
  });
});
