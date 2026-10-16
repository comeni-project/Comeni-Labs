import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const card = ({ showGapDetails = false } = {}) =>
  render(
    <StepProposalCard proposal={proposal()} progress={{ position: 4, total: 5, again: false }}
                      showGapDetails={showGapDetails} busy={false} onAccept={vi.fn()}
                      onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />,
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

  it("marks a registry gap and names the file to fix under Dev mode", () => {
    card({ showGapDetails: true });
    const gaps = screen.getByTestId("step-gaps");
    expect(gaps).toHaveTextContent("Registry information is incomplete");
    expect(gaps).toHaveTextContent("registry/tools/nf-core/multiqc/tool.yml");
  });

  it("draws no brief or gap section for a step that has none", () => {
    const bare = proposal();
    if (bare.block.kind === "step_proposal") {
      bare.block.brief = null;
      bare.block.gaps = [];
    }
    render(
      <StepProposalCard proposal={bare} progress={null} busy={false} onAccept={vi.fn()}
                        onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />,
    );
    expect(screen.queryByTestId("step-brief")).toBeNull();
    expect(screen.queryByTestId("step-gaps")).toBeNull();
  });
});

describe("changing a step (spec §14 of the consultant build)", () => {
  const withChoices = (): AuthoringProposal => {
    const p = proposal();
    p.options = ["keep", "alt_1", "fact_read_length"];
    if (p.block.kind === "step_proposal") {
      p.block.alternatives = [
        { id: "alt_1", label: "nf-core/hisat2/align@2.2.2",
          note: "adds hisat2_build; removes star_genomegenerate", recommended: false },
        { id: "alt_2", label: "lab/bad@1", note: "can't be built here: needs genome.gtf",
          recommended: false },
      ];
    }
    return p;
  };
  const show = (onAccept = vi.fn()) =>
    render(
      <StepProposalCard proposal={withChoices()} progress={{ position: 4, total: 5, again: false }} busy={false} onAccept={onAccept}
                        onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />,
    );

  it("offers each alternative with what it changes, and no Skip", () => {
    show();
    expect(screen.getByTestId("option-alt_1")).toHaveTextContent("adds hisat2_build");
    expect(screen.queryByTestId("reject-step")).toBeNull();
  });

  it("shows an alternative that cannot be built, and does not offer it", () => {
    show();
    expect(screen.getByTestId("refused-alt_2")).toHaveTextContent("can't be built here");
    expect(screen.queryByTestId("option-alt_2")).toBeNull();
  });

  it("asks for a fact the rule lacks, and sends it typed", async () => {
    const onAccept = vi.fn();
    show(onAccept);
    await userEvent.click(screen.getByTestId("option-fact_read_length"));
    await userEvent.type(screen.getByLabelText("read_length"), "50");
    await userEvent.click(screen.getByTestId("accept-step"));
    expect(onAccept).toHaveBeenCalledWith("fact_read_length", 50);
  });

  it("continues with the step as it is by default", async () => {
    const onAccept = vi.fn();
    show(onAccept);
    expect(screen.getByTestId("accept-step")).toHaveTextContent("Continue");
    await userEvent.click(screen.getByTestId("accept-step"));
    expect(onAccept).toHaveBeenCalledWith("keep", undefined);
  });
});


describe("a fact the tool reads (#341)", () => {
  function factCard(onAccept = vi.fn()) {
    const p = proposal();
    p.options = ["keep", "fact_strandedness"];
    if (p.block.kind === "step_proposal") {
      p.block.need = {
        kind: "fact", facts: ["strandedness"], choices: [],
        fact_values: { strandedness: ["forward", "reverse", "unstranded"] },
        fact_reasons: {
          strandedness: "nf-core/subread/featurecounts reads strandedness, and it is not known",
        },
      };
    }
    render(<StepProposalCard proposal={p} progress={null} busy={false} onAccept={onAccept}
                             onPreview={vi.fn()} onExplain={vi.fn()} onSelect={vi.fn()} />);
    return onAccept;
  }

  it("says why from its record, not a rule", () => {
    factCard();
    const option = screen.getByTestId("option-fact_strandedness");
    expect(option).toHaveTextContent("Tell me the strandedness");
    expect(option).toHaveTextContent("reads strandedness, and it is not known");
    expect(option).not.toHaveTextContent("the rule that picks this tool");
  });

  it("offers its values to pick, and sends the one picked", async () => {
    const onAccept = factCard();
    await userEvent.click(screen.getByTestId("option-fact_strandedness"));
    expect(screen.queryByRole("textbox")).toBeNull();
    await userEvent.click(screen.getByRole("radio", { name: "reverse" }));
    await userEvent.click(screen.getByTestId("accept-step"));
    expect(onAccept).toHaveBeenCalledWith("fact_strandedness", "reverse");
  });
});
