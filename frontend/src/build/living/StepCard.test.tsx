import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnsweredStep } from "../useBuilder";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { StepCard, type CardKind } from "./StepCard";

function sheet(overrides = {}) {
  const props = {
    node: "star_align", kind: "settings" as CardKind, onKind: vi.fn(),
    step: FAKE_STEPS.star_align as AnsweredStep, graph: FAKE_SESSION.graph,
    onSetParam: vi.fn(), onEdit: vi.fn(), onClose: vi.fn(), onSwitchInput: vi.fn(), onWhole: vi.fn(), ...overrides,
  };
  render(<QueryClientProvider client={new QueryClient()}><StepCard {...props} /></QueryClientProvider>);
  return props;
}

describe("a step's Settings card (issue 499)", () => {
  it("groups its values by how they were decided, the rule's folded", () => {
    sheet();
    const measured = screen.getByRole("region", { name: "Measured" });
    expect(within(measured).getByText("sjdbOverhang")).toBeInTheDocument();
    const settled = screen.getByRole("region", { name: "Settled by a rule" });
    expect(within(settled).queryByText("outSAMtype")).toBeNull();
    fireEvent.click(within(settled).getByRole("button", { name: /show/ }));
    expect(within(settled).getByText("outSAMtype")).toBeInTheDocument();
    expect(within(settled).getByText("twopassMode")).toBeInTheDocument();
  });

  it("shows a value's reason in place", () => {
    sheet();
    fireEvent.click(screen.getByRole("button", { name: /sjdbOverhang/ }));
    expect(screen.getByText("Read length is 151 bp, measured from your files, minus one.")).toBeInTheDocument();
  });

  it("asks what still needs the person first", () => {
    const open = { name: "strandedness", value: null, via: "ext", tier: 4, reason: "", because: "",
      axis_reason: "", optional: false, premise: [] };
    sheet({ step: { ...FAKE_STEPS.star_align, settings: [...FAKE_STEPS.star_align.settings, open] } });
    expect(screen.getByRole("region", { name: "Needs you" })).toHaveTextContent("strandedness");
  });

  it("puts an optional value under Optional, not Needs you (issue 494)", () => {
    const optional = { name: "prefix", value: null, via: "ext", tier: 4, reason: "", because: "",
      axis_reason: "", optional: true, premise: [] };
    sheet({ step: { ...FAKE_STEPS.star_align, settings: [...FAKE_STEPS.star_align.settings, optional] } });
    expect(screen.queryByRole("region", { name: "Needs you" })).toBeNull();
    expect(screen.getByRole("region", { name: "Optional to answer" })).toHaveTextContent("prefix");
  });

  it("closes from × and from Esc", () => {
    const p = sheet();
    fireEvent.click(screen.getByRole("button", { name: "Close the step" }));
    fireEvent.keyDown(screen.getByRole("region", { name: "step card STAR_ALIGN" }), { key: "Escape" });
    expect(p.onClose).toHaveBeenCalledTimes(2);
  });

  it("says what the AI chose and why, in its words (walk 2026-11-15)", () => {
    sheet({ aiChoices: [{ what: "chose nf-core/multiqc@1.35", because: "one report for every QC output" }],
            onReviewed: vi.fn() });
    const chose = screen.getByRole("region", { name: "What the AI chose" });
    expect(chose).toHaveTextContent("chose nf-core/multiqc@1.35");
    expect(chose).toHaveTextContent("one report for every QC output");
  });

  it("offers the step's other tools, Inputs only where it has any", () => {
    const p = sheet();
    expect(screen.queryByRole("button", { name: "Inputs…" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Swap tool…" }));
    expect(p.onKind).toHaveBeenCalledWith("swap");
  });
});

describe("a step's optional inputs (issue 460)", () => {
  const QUAST = {
    ...FAKE_STEPS.star_align, id: "quast", contract_id: "nf-core/quast@5.3.0", settings: [],
    ports: [
      { name: "consensus", type_id: "assembly.fasta", side: "in", met: true, optional: false, adds: [] },
      { name: "fasta", type_id: "genome.fasta", side: "in", met: true, optional: true, state: "off",
        reason: "off: not switched on", adds: ["transcriptome", "misassemblies", "unaligned"] },
    ],
  } as unknown as AnsweredStep;

  it("lists each optional input with its state, why, and what it adds", () => {
    sheet({ node: "quast", kind: "inputs", step: QUAST, onSwitchInput: vi.fn() });
    const region = screen.getByRole("region", { name: "Optional inputs" });
    expect(within(region).getByText("fasta")).toBeInTheDocument();
    expect(within(region).getByText(/adds transcriptome, misassemblies, unaligned/)).toBeInTheDocument();
    expect(within(region).getByText("off: not switched on")).toBeInTheDocument();
    expect(within(region).queryByText("consensus")).toBeNull();
    expect(within(region).getByRole("radio", { name: "Off" })).toBeChecked();
  });

  it("switches one on as the person's change", () => {
    const props = sheet({ node: "quast", kind: "inputs", step: QUAST, onSwitchInput: vi.fn() });
    fireEvent.click(screen.getByRole("radio", { name: "Optional" }));
    expect(props.onSwitchInput).toHaveBeenCalledWith("nf-core/quast@5.3.0", "fasta", "optional");
  });
});

describe("a step that runs on parts of each sample (issue 466)", () => {
  const SEARCH = {
    ...FAKE_STEPS.star_align, id: "search", contract_id: "lab/search@1.0.0", settings: [],
    parts: { on: true, splitter: "lab/split_reads@1.0.0", mergers: ["lab/merge_hits@1.0.0"],
             because: "lab/search@1.0.0 can run on parts of fastq.reads: lab/split_reads@1.0.0 splits each sample, and lab/merge_hits@1.0.0 merges its hits" },
  } as unknown as AnsweredStep;

  it("says how it is split and merged, and why", () => {
    sheet({ node: "search", kind: "inputs", step: SEARCH });
    const region = screen.getByRole("region", { name: "Runs in parts" });
    expect(within(region).getByText(/can run on parts of fastq.reads/)).toBeInTheDocument();
    expect(within(region).getByRole("checkbox", { name: "Run each sample whole" })).not.toBeChecked();
  });

  it("keeps it whole as the person's change, and back", () => {
    const props = sheet({ node: "search", kind: "inputs", step: SEARCH, onWhole: vi.fn() });
    fireEvent.click(screen.getByRole("checkbox", { name: "Run each sample whole" }));
    expect(props.onWhole).toHaveBeenCalledWith("lab/search@1.0.0", true);
  });

  it("offers it back when the step is kept whole", () => {
    const whole = { ...SEARCH, parts: { ...(SEARCH as { parts: object }).parts, on: false } } as unknown as AnsweredStep;
    const props = sheet({ node: "search", kind: "inputs", step: whole, onWhole: vi.fn() });
    const box = screen.getByRole("checkbox", { name: "Run each sample whole" });
    expect(box).toBeChecked();
    fireEvent.click(box);
    expect(props.onWhole).toHaveBeenCalledWith("lab/search@1.0.0", false);
  });

  it("says nothing for a step that cannot run on parts", () => {
    sheet({ kind: "inputs" });
    expect(screen.queryByRole("region", { name: "Runs in parts" })).toBeNull();
  });
});
