import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerLine } from "./StepLine";

describe("an answered line (Part I.2, issue 306)", () => {
  it("shows the question whole, wrapping rather than cut", () => {
    const asks = "Do you have the gene annotation (GTF) this genome's assembly was annotated with?";
    const decision = { id: "d1", kind: "gap", state: "accepted", by: "person", actor_kind: "person",
      chosen_option: "yes", chosen_contract: null, answer: null, at: "",
      block: { kind: "question", id: "q", asks, why_open: "", exhaustive: true,
        options: [{ id: "yes", label: "Yes", recommended: false }] } } as never;
    render(<AnswerLine decision={decision} />);
    const question = screen.getByText(asks);
    expect(question.className).not.toMatch(/\btruncate\b/);
  });
});
