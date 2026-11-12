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

describe("a samplesheet's fact columns (issue 466)", () => {
  const strandedness = {
    column: "strandedness", kind: "enum" as const, values: ["forward", "reverse", "unstranded"],
    minimum: null, maximum: null, required: true, auto: false,
    why: "you said strandedness differs between samples",
  };
  const readLength = {
    column: "read_length", kind: "integer" as const, values: [], minimum: 1, maximum: null,
    required: false, auto: true, why: "measured where left blank",
  };

  it("offers exactly a fact's values", () => {
    render(<Samplesheet columns={["reads_1"]} facts={[strandedness]} rows={[{}]} onChange={vi.fn()} />);
    const cell = screen.getByLabelText("strandedness for row 1") as HTMLSelectElement;
    expect(cell.tagName).toBe("SELECT");
    expect(Array.from(cell.options, (o) => o.value).filter(Boolean)).toEqual(
      ["forward", "reverse", "unstranded"]);
  });

  it("offers auto where the run measures a blank, and a number box with its bounds", () => {
    render(<Samplesheet columns={["reads_1"]} facts={[readLength]} rows={[{}]} onChange={vi.fn()} />);
    const cell = screen.getByLabelText("read_length for row 1") as HTMLInputElement;
    expect(cell.inputMode).toBe("numeric");
    expect(cell.placeholder).toBe("auto — measured in the run");
  });

  it("names a missing required fact, and lets an optional one stay blank", () => {
    const rows = [{ sample: "A", reads_1: "/a.fq" }];
    expect(incomplete(rows, ["reads_1"], [strandedness])).toEqual(["row 1: strandedness"]);
    expect(incomplete(rows, ["reads_1"], [readLength])).toEqual([]);
  });
});

describe("a fact cell is checked as the pipeline will check it (issue 466)", () => {
  const readLength = {
    column: "read_length", kind: "integer" as const, values: [], minimum: 1, maximum: 500,
    required: true, auto: false, why: "you said read length differs",
  };
  const row = (value: string) => [{ sample: "A", reads_1: "/a.fq", read_length: value }];

  it("names a number outside its bounds, or not whole, before the run", () => {
    expect(incomplete(row("0"), ["reads_1"], [readLength])).toEqual(["row 1: read_length is below 1"]);
    expect(incomplete(row("600"), ["reads_1"], [readLength])).toEqual(["row 1: read_length is above 500"]);
    expect(incomplete(row("150.5"), ["reads_1"], [readLength])).toEqual(["row 1: read_length is not a whole number"]);
    expect(incomplete(row("1,5"), ["reads_1"], [readLength])).toEqual(["row 1: read_length is not a number"]);
    expect(incomplete(row("150"), ["reads_1"], [readLength])).toEqual([]);
  });

  it("keeps what was typed, so a comma decimal is not silently blank", async () => {
    const onChange = vi.fn();
    render(<Samplesheet columns={[]} facts={[readLength]} rows={[{}]} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("read_length for row 1"), "1,5");
    expect(onChange).toHaveBeenLastCalledWith([{ read_length: "5" }]);
    expect((screen.getByLabelText("read_length for row 1") as HTMLInputElement).type).toBe("text");
  });
});

describe("a second file a row may leave blank (issue 466)", () => {
  it("is not asked for", () => {
    const rows = [{ sample: "A", reads_1: "/a.fq", reads_2: "" }];
    expect(incomplete(rows, ["reads_1", "reads_2"], [], ["reads_2"])).toEqual([]);
    expect(incomplete(rows, ["reads_1", "reads_2"], [])).toEqual(["row 1: reads_2"]);
  });
});
