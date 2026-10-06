import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringProposal } from "../../../api/types";
import { StepProposalCard } from "./StepProposalCard";

/** The step card carries its brief, its need and its registry gaps (spec §13 of the consultant
 *  build), each line as the engine wrote it. Part 5 designs the card; this is its content. */

function proposal(): AuthoringProposal {
  return {
    id: "p1",
    kind: "step",
    draft_revision: 3,
    options: ["keep"],
    edges: [],
    block: {
      kind: "step_proposal",
      id: "step-multiqc",
      node: "multiqc",
      contract: "nf-core/multiqc@1.25.1",
      consumes: ["qc.report"],
      produces: ["qc.report"],
      reason: "uncontested",
      tier: 2,
      alternatives: [],
      brief: {
        does: { text: "MultiQC gathers every report into one.", source: "curated" },
        why: [
          { text: "uncontested", source: "engine" },
          { text: "one report a person can read", source: "engine" },
        ],
        makes: [{ text: "quality reports", source: "curated" }],
        check: [{ text: "read_length is 150, measured by fastq@1.1.0", source: "engine" }],
      },
      need: { kind: "fact", facts: ["read_length"], choices: [] },
      gaps: [
        {
          kind: "no_description",
          subject: "nf-core/multiqc",
          fix: "registry/tools/nf-core/multiqc/tool.yml",
        },
      ],
    },
  } as AuthoringProposal;
}

const card = () =>
  render(
    <StepProposalCard proposal={proposal()} position={4} busy={false} onAccept={vi.fn()}
                      onReject={vi.fn()} onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />,
  );

describe("the step card's brief", () => {
  it("shows the four fields, each line as written", () => {
    card();
    const brief = screen.getByTestId("step-brief");
    expect(brief).toHaveTextContent("What it does");
    expect(brief).toHaveTextContent("MultiQC gathers every report into one.");
    expect(brief).toHaveTextContent("Why it's here");
    expect(brief).toHaveTextContent("one report a person can read");
    expect(brief).toHaveTextContent("What it makes");
    expect(brief).toHaveTextContent("quality reports");
    expect(brief).toHaveTextContent("Check");
    expect(brief).toHaveTextContent("read_length is 150, measured by fastq@1.1.0");
  });

  it("marks a registry gap and names the file to fix", () => {
    card();
    const gaps = screen.getByTestId("step-gaps");
    expect(gaps).toHaveTextContent("Registry gap");
    expect(gaps).toHaveTextContent("registry/tools/nf-core/multiqc/tool.yml");
  });

  it("draws no brief or gap section for a step that has none", () => {
    const bare = proposal();
    if (bare.block.kind === "step_proposal") {
      bare.block.brief = null;
      bare.block.gaps = [];
    }
    render(
      <StepProposalCard proposal={bare} position={1} busy={false} onAccept={vi.fn()}
                        onReject={vi.fn()} onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />,
    );
    expect(screen.queryByTestId("step-brief")).toBeNull();
    expect(screen.queryByTestId("step-gaps")).toBeNull();
  });
});
