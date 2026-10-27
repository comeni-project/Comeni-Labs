import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { StepStrip } from "./StepStrip";

describe("the step strip above the conversation (one builder plan 3)", () => {
  it("names each planned step, the one on offer marked, and where the walk is", () => {
    render(<StepStrip session={FAKE_SESSION} selected={null} onSelect={vi.fn()} />);
    const strip = screen.getByRole("navigation", { name: "the plan" });
    expect(strip).toHaveTextContent("Step 4 of 5");
    expect(screen.getAllByRole("button").slice(0, -1).map((b) => b.textContent)).toEqual([
      "STAR_GENOMEGENERATE", "TRIMGALORE", "STAR_ALIGN", "SAMTOOLS_SORT", "SUBREAD_FEATURECOUNTS",
    ]);
    expect(screen.getByRole("button", { name: "SAMTOOLS_SORT" })).toHaveAttribute("aria-current", "step");
  });

  it("opens the whole plan from where the walk is", () => {
    const onTogglePlan = vi.fn();
    render(<StepStrip session={FAKE_SESSION} selected={null} onSelect={vi.fn()} onTogglePlan={onTogglePlan} />);
    fireEvent.click(screen.getByRole("button", { name: "the whole plan" }));
    expect(onTogglePlan).toHaveBeenCalled();
  });

  it("opens a step with one click", () => {
    const onSelect = vi.fn();
    render(<StepStrip session={FAKE_SESSION} selected={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "STAR_ALIGN" }));
    expect(onSelect).toHaveBeenCalledWith("star_align");
  });

  it("says Describing while there is nothing planned yet", () => {
    const describing = { ...FAKE_SESSION, phase: "gathering", history: [], pending_proposal: null,
      progress: null } as unknown as AuthoringSession;
    render(<StepStrip session={describing} selected={null} onSelect={vi.fn()} />);
    expect(screen.getByRole("navigation", { name: "the plan" })).toHaveTextContent("Describing");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
