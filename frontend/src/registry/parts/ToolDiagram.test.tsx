import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ToolDiagram } from "./ToolDiagram";

const shape = {
  job: null,
  inputs: [{ key: "questions:input_type:fasta", name: "fasta", type: "genome.fasta" }],
  outputs: [{ key: "questions:output_type:tsv", name: "tsv", type: null }],
};

it("draws each pin with its type, or says it is not decided", () => {
  render(<ToolDiagram name="quast" shape={shape} onPick={() => {}} />);
  expect(screen.getByRole("button", { name: /fasta.*genome\.fasta/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: /tsv.*not decided/ })).toBeTruthy();
  expect(screen.getByText("job not decided")).toBeTruthy();
});

it("picking a pin says which item", () => {
  const onPick = vi.fn();
  render(<ToolDiagram name="quast" shape={shape} onPick={onPick} />);
  fireEvent.click(screen.getByRole("button", { name: /tsv/ }));
  expect(onPick).toHaveBeenCalledWith("questions:output_type:tsv");
});

it("marks the pin in focus", () => {
  render(<ToolDiagram name="quast" shape={shape} focus="questions:input_type:fasta" onPick={() => {}} />);
  expect(screen.getByRole("button", { name: /fasta/ }).getAttribute("aria-pressed")).toBe("true");
});

it("draws an optional input hollow and labelled, and a conditional output with its condition", () => {
  render(<ToolDiagram name="quast" onPick={() => {}} shape={{
    job: null,
    inputs: [{ key: "contract:input:fasta", name: "fasta", type: "genome.fasta", optional: true }],
    outputs: [{ key: "contract:output:unaligned", name: "unaligned", type: "qc.report", only: "only with fasta" }],
  }} />);
  const fasta = screen.getByRole("button", { name: /fasta.*optional/ });
  expect(fasta.getAttribute("data-optional")).toBe("true");
  expect(screen.getByRole("button", { name: /unaligned.*only with fasta/ })).toBeTruthy();
});
