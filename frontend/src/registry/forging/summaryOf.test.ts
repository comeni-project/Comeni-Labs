import { expect, it } from "vitest";

import { summaryOf } from "./PieceItems";

it("reads a port's optional and conditional parts (issue 460)", () => {
  expect(summaryOf("contract:input:fasta", { type_id: "genome.fasta", required: false }))
    .toBe("genome.fasta · optional");
  expect(summaryOf("contract:output:unaligned", { type_id: "qc.report", produced_when: { "given.fasta": "present" } }))
    .toBe("qc.report · only with fasta");
});

it("reads a constraint item by its sentence when the engine gives one", () => {
  expect(summaryOf("contract:constraint:row1", { requires: ["fasta"], because: "x" },
                   "`gff` is used only with `fasta` (x)")).toBe("`gff` is used only with `fasta` (x)");
});
