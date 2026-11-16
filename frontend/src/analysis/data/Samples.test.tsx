import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";

vi.mock("../../api/client", () => ({
  get: vi.fn(async () => ({ names: { "fastq.reads": "sequencing reads (FASTQ)", "assembly.fasta": "Assembly sequences (FASTA)" } })),
}));
import { Samples } from "./Samples";
import type { AnalysisData } from "./types";

function actions() {
  return { setRule: vi.fn(async () => undefined), confirmRule: vi.fn(), undoFix: vi.fn(),
           setCell: vi.fn(), addColumn: vi.fn() };
}

function samples(data: AnalysisData = analysis(), act = actions()) {
  render(<QueryClientProvider client={new QueryClient()}><Samples data={data} {...act} /></QueryClientProvider>);
  return act;
}

const withRule = (over: Partial<AnalysisData> = {}) => analysis({
  scan: { state: "done", done: 5, total: 5, error: null,
          examples: [["L01_R1.fq.gz", "L01", "1"], ["L01_R2.fq.gz", "L01", "2"], ["L02_R1.fq.gz", "L02", "1"]] },
  rule_result: { samples: 2, unfit: 1, examples: [] }, ...over });

it("reading rule shows three examples and the sample and unfit counts", () => {
  samples(withRule());
  const rule = screen.getByRole("region", { name: "How the samples were read" });
  expect(within(rule).getAllByTestId("rule-example")).toHaveLength(3);
  expect(within(rule).getByText(/2 samples/)).toBeTruthy();
  expect(within(rule).getByText(/1 file did not fit/)).toBeTruthy();
});

it("looks right confirms; change the rule submits a pattern", () => {
  const act = samples(withRule());
  fireEvent.click(screen.getByRole("button", { name: "Looks right" }));
  expect(act.confirmRule).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Change the rule" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Reading rule" }), { target: { value: "{sample}_R{read}.fq.gz" } });
  fireEvent.click(screen.getByRole("button", { name: "Use this rule" }));
  expect(act.setRule).toHaveBeenCalledWith("{sample}_R{read}.fq.gz");
});

it("a refused rule keeps the editor open", async () => {
  const act = actions();
  act.setRule = vi.fn(async () => { throw new Error("MI0223"); });
  samples(withRule(), act);
  fireEvent.click(screen.getByRole("button", { name: "Change the rule" }));
  fireEvent.click(screen.getByRole("button", { name: "Use this rule" }));
  expect(await screen.findByRole("textbox", { name: "Reading rule" })).toBeTruthy();
});

it("a confirmed AI rule no longer reads as AI, and its reason shows", () => {
  samples(withRule({ rule: { pattern: "{sample}_{read}.fq", origin: "ai", confirmed: true, reason: "names end _1/_2" } }));
  const rule = screen.getByRole("region", { name: "How the samples were read" });
  expect(within(rule).queryByText("AI")).toBeNull();
  expect(within(rule).getByText(/names end _1\/_2/)).toBeTruthy();
});

it("an AI rule is tagged AI until confirmed", () => {
  samples(withRule({ rule: { pattern: "{sample}_{read}.fq", origin: "ai", confirmed: false, reason: "names" } }));
  expect(within(screen.getByRole("region", { name: "How the samples were read" })).getByText("AI")).toBeTruthy();
});

it("columns follow the data: paired reads get read 1 and read 2, assemblies one file", () => {
  samples();
  expect(screen.getByRole("columnheader", { name: "Read 1" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Read 2" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Read length" })).toBeTruthy();
  const one = analysis({ samples: [{ name: "a", files: ["/d/a.fasta"], outcome: "measured", type_id: null,
                                     left_out: false, facts: [] }] } as Partial<AnalysisData>);
  document.body.innerHTML = "";
  samples(one);
  expect(screen.getByRole("columnheader", { name: "File" })).toBeTruthy();
  expect(screen.queryByRole("columnheader", { name: "Read 2" })).toBeNull();
});

it("to check filter shows only flagged samples", () => {
  const data = analysis({ checks: [{ sample: "L02", kind: "odd_fact", detail: "Read length is 50",
                                     fixes: [{ kind: "leave_out", sample: "L02", file: null, by: "you", reason: null }] }] });
  samples(data);
  fireEvent.click(screen.getByRole("button", { name: /To check/ }));
  const names = screen.getAllByRole("row").slice(1).map((r) => r.querySelector("[role=cell]")?.textContent);
  expect(names).toEqual(["L02"]);
});

it("a left-out sample says so and can be brought back", () => {
  const data = analysis({
    samples: [{ ...analysis().samples[0], left_out: true }, analysis().samples[1]],
    fixes: [{ kind: "leave_out", sample: "L01", file: null, by: "you", reason: null }],
  });
  const act = samples(data);
  fireEvent.click(screen.getByRole("button", { name: "Bring L01 back" }));
  expect(act.undoFix).toHaveBeenCalledWith(0);
});

it("add column prompts for a name and stores values", () => {
  const act = samples(analysis({ columns: { condition: { L01: "treated" } } }));
  expect(screen.getByRole("columnheader", { name: "condition" })).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox", { name: "condition for L02" }), { target: { value: "control" } });
  fireEvent.blur(screen.getByRole("textbox", { name: "condition for L02" }));
  expect(act.setCell).toHaveBeenCalledWith("condition", "L02", "control");
  fireEvent.click(screen.getByRole("button", { name: "+ Add column" }));
  fireEvent.change(screen.getByRole("textbox", { name: "New column" }), { target: { value: "batch" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(act.addColumn).toHaveBeenCalledWith("batch");
});

it("assemblies: lengths read in Mb by their unit, counts with separators, one sample per file (issue 532)", () => {
  const base = analysis();
  samples(analysis({
    samples: [{ name: "BAC47", files: ["/d/BAC47.fna"], outcome: "measured", type_id: "assembly.fasta", left_out: false,
                facts: [{ measurement: "assembly_length", value: 2837243, coverage: "all", pieces: [] },
                        { measurement: "contigs", value: 12065, coverage: "all", pieces: [] },
                        { measurement: "n50", value: 85010, coverage: "all", pieces: [] }] }],
    rule_result: { samples: 1, unfit: 0, examples: [] },
    summary: { ...base.summary, compare_by: [
      { measurement: "assembly_length", label: "Assembly length", unit: "bp", values: [], median: 0 },
      { measurement: "n50", label: "N50", unit: "bp", values: [], median: 0 }] },
  }));
  expect(screen.getByText("2.84 Mb")).toBeTruthy();
  expect(screen.getByText("85 kb")).toBeTruthy();
  expect(screen.getByText("12,065")).toBeTruthy();
  expect(screen.getByText("one file each, named by the file")).toBeTruthy();
  expect(screen.queryByText(/read 1 and 2/)).toBeNull();
});

it("a number column draws a bar, amber only where that measurement is flagged (board 2026-11-16)", () => {
  const fact = (measurement: string, value: number) => ({ measurement, value, coverage: "all" as const, pieces: [] });
  const asm = (name: string, contigs: number, length: number) => ({
    name, files: [`/d/${name}.fna`], outcome: "measured" as const, type_id: "assembly.fasta", left_out: false,
    facts: [fact("contigs", contigs), fact("assembly_length", length)] });
  samples(analysis({
    samples: [asm("N315", 2, 2839469), asm("BAC47", 65, 2837243)],
    checks: [{ sample: "BAC47", kind: "odd_fact", measurement: "contigs", detail: "Contigs is 65; the median is 4", fixes: [] }],
    rule_result: { samples: 2, unfit: 0, examples: [] },
  }));
  const amber = screen.getAllByTestId("fact-bar").filter((b) => b.className.includes("bg-measured"));
  expect(amber).toHaveLength(1);
  expect(amber[0].closest("[role='row']")).toHaveTextContent("BAC47");
});

it("two kinds of data get one tab each, with that kind's columns", async () => {
  const base = analysis();
  samples(analysis({
    samples: [...base.samples, { name: "ASM1", files: ["/d/ASM1.fna"], outcome: "measured", type_id: "assembly.fasta", left_out: false,
                                 facts: [{ measurement: "contigs", value: 3, coverage: "all", pieces: [] }] }],
  }));
  const tabs = await screen.findByRole("group", { name: "Kind of data" });
  expect(within(tabs).getAllByRole("button")).toHaveLength(2);
  expect(screen.queryByText("ASM1")).toBeNull();
  fireEvent.click(await within(tabs).findByRole("button", { name: /Assembly/ }));
  expect(screen.getByText("ASM1")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Contigs" })).toBeTruthy();
});
