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

it("keeps the content state and the contract's file format on an output pin", () => {
  const shape = toolShape([
    item("questions:output_type:tsv", { choice: "qc.report::assembly" }, "approved"),
    item("contract:output:tsv", { type_id: "qc.report::assembly", format: ["tsv"] }),
  ]);
  expect(shape.outputs[0]).toMatchObject({ type: "qc.report::assembly", format: ["tsv"] });
});

it("draws the existing contract when a re-forge has no port questions yet", () => {
  const shape = toolShape([
    item("contract:process", { roles: ["alignment"] }),
    item("contract:input:reads", { type_id: "fastq.reads" }),
    item("contract:output:bam", { type_id: "alignment.bam", format: ["bam"] }),
  ]);
  expect(shape.job).toBe("alignment");
  expect(shape.inputs).toEqual([{ key: "contract:input:reads", name: "reads", type: "fastq.reads" }]);
  expect(shape.outputs).toEqual([{ key: "contract:output:bam", name: "bam", type: "alignment.bam", format: ["bam"] }]);
});

it("marks an optional input and says when a conditional output is written (issue 460)", () => {
  const shape = toolShape([
    item("questions:input_type:fasta", { choice: "genome.fasta" }, "approved"),
    item("contract:input:fasta", { position: 1, name: "fasta", type_id: "genome.fasta", required: false }),
    item("questions:output_type:misassemblies", { choice: "qc.report" }, "approved"),
    item("contract:output:misassemblies", { position: 3, name: "misassemblies", type_id: "qc.report",
      produced_when: { "given.fasta": "present" } }),
  ]);
  expect(shape.inputs[0]).toMatchObject({ name: "fasta", optional: true });
  expect(shape.outputs[0]).toMatchObject({ name: "misassemblies", only: "only with fasta" });
});
