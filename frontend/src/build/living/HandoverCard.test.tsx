import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import type { AnsweredStep } from "../useBuilder";
import { HandoverCard } from "./blocks/HandoverCard";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";

const goal = { ...FAKE_SESSION.history[0], block: { ...FAKE_SESSION.history[0].block,
  goal: { have: [{ type_id: "fastq.reads", states: [] }, { type_id: "genome.fasta", states: [] }], want: ["counts.matrix"] } } };
const done = { ...FAKE_SESSION, phase: "complete", pending_proposal: null,
  history: [goal, ...FAKE_SESSION.history.slice(1)] } as unknown as AuthoringSession;
const steps = FAKE_STEPS as unknown as Record<string, AnsweredStep>;
const openStep = { ...steps, trimgalore: { ...steps.trimgalore, settings: [{ name: "clip_r1", value: null,
  via: "ext", tier: 4, reason: "", because: "", axis_reason: "", optional: false, premise: [] }] } } as
  unknown as Record<string, AnsweredStep>;

function card(overrides = {}) {
  const props = { session: done, steps, summary: "You'll get: counts.matrix. Decided: 6 at tier 2 by registry.",
    runnable: true, onRun: vi.fn(), onView: vi.fn(), onSelect: vi.fn(), ...overrides };
  render(<HandoverCard {...props} />);
  return props;
}

describe("the hand-over (issue 393)", () => {
  it("says what was built: inputs to outputs, then the steps in order", () => {
    card();
    const built = screen.getByRole("region", { name: "What you built" });
    expect(built).toHaveTextContent("fastq.reads, genome.fasta → counts.matrix");
    expect(built).toHaveTextContent("STAR_GENOMEGENERATE → TRIMGALORE → STAR_ALIGN");
  });

  it("counts how its values were decided, each count opening the pipeline file", () => {
    const p = card();
    const how = screen.getByRole("region", { name: "How its values were decided" });
    expect(within(how).getAllByRole("button").map((b) => b.textContent)).toEqual(["2 settled", "1 measured"]);
    fireEvent.click(within(how).getByRole("button", { name: "1 measured" }));
    expect(p.onView).toHaveBeenCalledWith("artifact");
  });

  it("lists what still needs you, each opening its step, and locks Run with the reason", () => {
    const p = card({ steps: openStep });
    const needs = screen.getByRole("region", { name: "What still needs you" });
    fireEvent.click(within(needs).getByRole("button", { name: "TRIMGALORE · 1 value" }));
    expect(p.onSelect).toHaveBeenCalledWith("trimgalore");
    expect(screen.getByRole("button", { name: "Run it" })).toBeDisabled();
    expect(screen.getByText("Answer the values above first.")).toBeInTheDocument();
  });

  it("says nothing needs you by drawing no such part, and runs", () => {
    const p = card();
    expect(screen.queryByRole("region", { name: "What still needs you" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Run it" }));
    expect(p.onRun).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Look at the pipeline file" }));
    expect(p.onView).toHaveBeenCalledWith("artifact");
    expect(screen.getByText(/or keep asking below/)).toBeInTheDocument();
  });

  it("keeps the engine's own sentence under the card", () => {
    card();
    expect(screen.getByText("You'll get: counts.matrix. Decided: 6 at tier 2 by registry.")).toBeInTheDocument();
  });
});
