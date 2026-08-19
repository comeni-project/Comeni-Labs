import { render as raw, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { describe, expect, it } from "vitest";

import type { OpenQuestion } from "./QueueRow";
import { QueueRow } from "./QueueRow";

const q = (over: Partial<OpenQuestion> = {}): OpenQuestion => ({
  // `kind` is required on the generated type since phase 5 added drift rows. A helper that
  // omitted it compiled under `tsc --noEmit` and failed under `tsc -b`.
  kind: "question",
  subject: "consumes[0].type_id",
  what: "what arrives on channel 0",
  why_open: "nf-core declares it as type: file",
  band: "routing",
  asked_by: ["picard/markduplicates", "samtools/index", "samtools/sort"],
  candidates: [],
  closed: true,
  evidence: [],
  suggested: null,
  ...over,
});

/** A row links to its question, so it needs router context. Wrapping here rather than
 *  changing the component: the link is the point — it is what made the row usable. */
const render = (ui: React.ReactNode) => raw(<MemoryRouter>{ui}</MemoryRouter>);

describe("QueueRow", () => {
  it("shows how many drafts ask one question", () => {
    // The throughput move made visible: one row, three modules, answered once.
    render(<QueueRow q={q()} />);
    expect(screen.getByText(/3 modules/)).toBeTruthy();
  });

  it("says 'module' rather than 'modules' when only one asks", () => {
    render(<QueueRow q={q({ asked_by: ["fastqc"] })} />);
    expect(screen.getByText(/1 module$/)).toBeTruthy();
  });

  it("demotes a cosmetic row in the markup, not in a reviewer's discipline", () => {
    // ~60% accurate and renamed in seconds. The design deprioritises it; a data
    // attribute is where that either is or is not true.
    const { container } = render(<QueueRow q={q({ band: "cosmetic" })} />);
    expect(container.querySelector("[data-band='cosmetic']")).toBeTruthy();
  });

  it("calls a question with a suggestion Confirm, and one without it Ask", () => {
    render(<QueueRow q={q({ suggested: "alignment.bam" })} />);
    expect(screen.getByText("Confirm")).toBeTruthy();
  });

  it("labels an unanswered question Ask", () => {
    render(<QueueRow q={q()} />);
    expect(screen.getByText("Ask")).toBeTruthy();
  });
});
