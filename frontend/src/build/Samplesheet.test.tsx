import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { incomplete, Samplesheet } from "./Samplesheet";

/** Plan 5B §5.3. **`params.input` is one null whether it is a glob or a CSV path**, so the form
 *  has to be told which — and a table is the only control that can ask for a table. */
describe("the samplesheet builder", () => {
  it("draws a column per per-sample input, plus the identifier that ties them", () => {
    // `sample` is not one of the artifact's columns and never will be: those are the *file*
    // columns each sample supplies, and this is the thing that says which sample they belong to.
    render(<Samplesheet columns={["reads_1", "reads_2", "gtf"]} rows={[{}]} onChange={vi.fn()} />);
    for (const column of ["sample", "reads_1", "reads_2", "gtf"]) {
      expect(screen.getByLabelText(`${column} for row 1`)).toBeTruthy();
    }
  });

  it("adds a sample without touching the ones already there", async () => {
    const onChange = vi.fn();
    render(<Samplesheet columns={["gtf"]} rows={[{ sample: "A", gtf: "/a.gtf" }]} onChange={onChange} />);

    await userEvent.click(screen.getByTestId("add-row"));

    expect(onChange).toHaveBeenCalledWith([
      { sample: "A", gtf: "/a.gtf" },
      { sample: "", gtf: "" },
    ]);
  });

  it("will not remove the last row", async () => {
    // A table with a header and nothing to fill reads as broken rather than as empty, and
    // `incomplete` cannot name what is missing in a table that has no rows.
    const onChange = vi.fn();
    render(<Samplesheet columns={["gtf"]} rows={[{ sample: "A" }]} onChange={onChange} />);

    await userEvent.click(screen.getByTestId("drop-row"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("edits one cell and leaves the rest of the row alone", async () => {
    const onChange = vi.fn();
    render(
      <Samplesheet columns={["gtf"]} rows={[{ sample: "A", gtf: "/a.gtf" }]} onChange={onChange} />,
    );

    await userEvent.type(screen.getByLabelText("sample for row 1"), "B");
    expect(onChange).toHaveBeenCalledWith([{ sample: "AB", gtf: "/a.gtf" }]);
  });
});

describe("incomplete", () => {
  it("names the row and the fields, rather than counting them", () => {
    // A count tells somebody there is a problem; a name tells them where. Same argument
    // `useSubmit.unfilled` makes about the start button.
    expect(incomplete([{ sample: "A", gtf: "" }, { sample: "", gtf: "/b.gtf" }], ["gtf"])).toEqual([
      "row 1: gtf",
      "row 2: sample",
    ]);
  });

  it("is empty when every row is filled", () => {
    expect(incomplete([{ sample: "A", gtf: "/a.gtf" }], ["gtf"])).toEqual([]);
  });

  it("counts whitespace as missing", () => {
    // A path of spaces is a path Nextflow will fail on, minutes later, with a message about a
    // file rather than about the form that accepted it.
    expect(incomplete([{ sample: "  ", gtf: "/a.gtf" }], ["gtf"])).toEqual(["row 1: sample"]);
  });
});
