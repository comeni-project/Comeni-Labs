import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Sources, terminalOutputs } from "./Sources";

/** Two `fastq.reads` inputs, which is the case the whole feature exists for. */
const DATA = {
  steps: [
    {
      id: "star_align",
      ports: [
        { name: "reads", type_id: "fastq.reads", side: "in", met: true, states: [] },
        { name: "control", type_id: "fastq.reads", side: "in", met: true, states: [] },
        { name: "bam", type_id: "alignment.bam", side: "out", met: true, states: [] },
      ],
    },
  ],
  layout: { nodes: [{ id: "star_align", x: 0, y: 0, rank: 0 }], wires: [] },
};

describe("naming a socket", () => {
  it("is what makes two inputs of one type tellable apart", async () => {
    // **The case the feature exists for.** `fastq.reads` twice says nothing about which is
    // which, and a person cannot draw a tumour/normal pipeline they can read without it.
    const rename = vi.fn();
    render(<Sources data={DATA as never} offsets={{}} labels={{}} onRename={rename} />);

    const fields = screen.getAllByTestId("socket-name");
    await userEvent.type(fields[0], "t");

    expect(rename).toHaveBeenCalledWith("star_align.reads", "t");
  });

  it("shows the port's own name until somebody types one", () => {
    // A placeholder rather than a value: an empty label is an *absence*, and prefilling the
    // port name would make every socket look renamed and put a value in the draft that nobody
    // chose. Absence is absence — the same rule the run sheet's slots follow.
    render(<Sources data={DATA as never} offsets={{}} labels={{}} onRename={vi.fn()} />);
    const fields = screen.getAllByTestId("socket-name") as HTMLInputElement[];
    expect(fields[0].value).toBe("");
    expect(fields[0].placeholder).toBe("reads");
  });

  it("shows the label once there is one, on an output as well as an input", () => {
    render(
      <Sources
        data={DATA as never}
        offsets={{}}
        labels={{ "star_align.reads": "tumour", "star_align.bam": "aligned tumour" }}
        onRename={vi.fn()}
      />,
    );
    const values = (screen.getAllByTestId("socket-name") as HTMLInputElement[]).map((f) => f.value);
    expect(values).toContain("tumour");
    expect(values).toContain("aligned tumour");
  });

  it("offers no field at all when nothing can be renamed", () => {
    // `Sources` renders read-only wherever there is no `onRename` — the run sheet reuses the
    // same derivation and must not become a place a person edits a pipeline.
    const { container } = render(<Sources data={DATA as never} offsets={{}} />);
    expect(container.querySelectorAll("[data-testid=socket-name]").length).toBe(0);
    expect(container.textContent).toMatch(/reads/);
  });

  it("still refuses a path, which is what the socket is not for", () => {
    // `norule.test.ts` holds the general rule; this is the specific one for a control that did
    // not exist when that rule was written. **A rename field is the first editable thing on
    // this canvas**, and invariant 15 is why every other one was refused: the socket carries a
    // TYPE and never a path, and a label is a reading aid over that, not a way in.
    render(
      <Sources
        data={DATA as never}
        offsets={{}}
        labels={{ "star_align.reads": "tumour" }}
        onRename={vi.fn()}
      />,
    );
    // What a person types is theirs; what matters is that it reaches no artifact, which
    // `tests/test_draft_labels.py` asserts against the emitted `.nf` and `pipeline.yml`.
    expect(screen.getAllByTestId("socket-name").length).toBeGreaterThan(0);
  });
});

describe("terminalOutputs", () => {
  it("is what `goal_of` calls `want` — every produces nothing consumes", () => {
    expect(terminalOutputs(DATA as never).map((o) => o.key)).toEqual(["star_align.bam"]);
  });

  it("is empty when everything is consumed", () => {
    const wired = {
      ...DATA,
      steps: [
        ...DATA.steps,
        {
          id: "samtools_sort",
          ports: [{ name: "bam", type_id: "alignment.bam", side: "in", met: true, states: [] }],
        },
      ],
      layout: {
        ...DATA.layout,
        wires: [
          { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" },
        ],
      },
    };
    expect(terminalOutputs(wired as never)).toEqual([]);
  });
});
