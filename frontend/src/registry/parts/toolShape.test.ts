import { expect, it } from "vitest";

import type { ItemView } from "../forging/useAdaptation";
import { toolShape } from "./toolShape";

function item(key: string, value: unknown, status = "proposed"): ItemView {
  return { key, piece: "questions", status, value, current_n: 1, revisions: [] } as unknown as ItemView;
}

it("draws each input and output a question names, and the job", () => {
  const shape = toolShape([
    item("questions:role", { choice: "qc_per_sample" }, "approved"),
    item("questions:input_type:consensus", { choice: "assembly.fasta" }, "approved"),
    item("questions:input_type:fasta", { asks: "What kind of file?" }),
    item("questions:output_type:tsv", { asks: "What kind of file?" }),
  ]);
  expect(shape.job).toBe("qc_per_sample");
  expect(shape.inputs).toEqual([
    { key: "questions:input_type:consensus", name: "consensus", type: "assembly.fasta" },
    { key: "questions:input_type:fasta", name: "fasta", type: null },
  ]);
  expect(shape.outputs).toEqual([{ key: "questions:output_type:tsv", name: "tsv", type: null }]);
});

it("leaves out a removed question and anything that is not a port", () => {
  const shape = toolShape([
    item("questions:input_type:meta", { choice: "x" }, "removed"),
    item("questions:competition", { asks: "Does it compete?" }),
    item("contract:process", { nf_process: "QUAST" }),
  ]);
  expect(shape.inputs).toEqual([]);
  expect(shape.outputs).toEqual([]);
  expect(shape.job).toBeNull();
});
