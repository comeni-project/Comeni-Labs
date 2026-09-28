import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringProposal } from "../../api/types";
import { GapCard } from "./blocks/GapCard";

/** 14.7.3: the engine asks for what the want needs, one gap at a time, and a click answers. */

const gap = (options: [string, string][], asks: string): AuthoringProposal => ({
  id: "p-gap",
  kind: "gap",
  draft_revision: 0,
  options: options.map(([id]) => id).sort(),
  edges: [],
  block: {
    kind: "question",
    id: "gap-3",
    asks,
    why_open: "a step reads it to decide",
    options: options.map(([id, label]) => ({ id, label, recommended: false })),
    exhaustive: true,
  },
});

const PAIRED = gap(
  [["yes", "Yes"], ["no", "No"], ["not_sure", "Not sure"], ["cant_share", "I can't share it"]],
  "Whether the library was sequenced paired-end?",
);
const LENGTH = gap(
  [["value", "Type it (bp)"], ["not_sure", "Not sure"], ["cant_share", "I can't share it"]],
  "Sequenced read length?",
);

describe("a gap card", () => {
  it("draws a closed question's options as buttons, and a click answers it", () => {
    const onAnswer = vi.fn();
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onAnswer).toHaveBeenCalledWith("yes", undefined);
  });

  it("says why the engine is asking", () => {
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("a step reads it to decide")).toBeInTheDocument();
  });

  it("draws a number field for an open value, with not sure and can't share beside it", () => {
    const onAnswer = vi.fn();
    render(<GapCard proposal={LENGTH} busy={false} onAnswer={onAnswer} />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "Type it (bp)" }), {
      target: { value: "150" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Use this" }));
    expect(onAnswer).toHaveBeenCalledWith("value", 150);
    expect(screen.getByRole("button", { name: "Not sure" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I can't share it" })).toBeInTheDocument();
  });

  it("cannot send an empty value", () => {
    render(<GapCard proposal={LENGTH} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Use this" })).toBeDisabled();
  });
});
