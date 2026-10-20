import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { StepLine } from "./StepLine";

function line(session: AuthoringSession = FAKE_SESSION, selected: string | null = null) {
  const onSelect = vi.fn();
  render(<StepLine session={session} selected={selected} onSelect={onSelect} />);
  const rows = within(screen.getByRole("list", { name: "the plan" })).getAllByRole("listitem");
  return { onSelect, rows };
}

describe("the step line", () => {
  it("lists the goal, each decided step with who settled it, then the step on offer", () => {
    const { rows } = line();
    expect(rows.length).toBe(6);
    expect(rows[0]).toHaveTextContent(/Goal.*a gene-level counts matrix.*you confirmed/);
    expect(rows[1]).toHaveTextContent(/STAR_GENOMEGENERATE.*step 1.*you chose/);
    expect(rows[3]).toHaveTextContent(/STAR_ALIGN.*step 3.*you chose/);
    expect(rows[4]).toHaveTextContent(/SAMTOOLS_SORT.*step 4.*waiting for you/);
    expect(rows[4]).toHaveAttribute("aria-current", "step");
  });

  it("counts the steps still to come, because the engine has not named them yet", () => {
    const { rows } = line();
    expect(rows[5]).toHaveTextContent("1 more step");
  });

  it("says nothing of steps to come when nothing is on offer", () => {
    const { rows } = line({ ...FAKE_SESSION, pending_proposal: null,
      progress: { reviewed: 5, total: 5, active: null } } as AuthoringSession);
    expect(rows.map((r) => r.textContent).join(" ")).not.toMatch(/more step/);
  });

  it("says when a step was skipped or its answers changed", () => {
    const history = [
      ...FAKE_SESSION.history,
      { ...FAKE_SESSION.history[3], id: "h-x", state: "stale" },
    ] as AuthoringSession["history"];
    const { rows } = line({ ...FAKE_SESSION, history } as AuthoringSession);
    expect(rows[4]).toHaveTextContent("answers changed");
  });

  it("selects a decided step on the canvas, and marks the one selected", () => {
    const { onSelect, rows } = line(FAKE_SESSION, "trimgalore");
    expect(within(rows[2]).getByRole("button")).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(rows[3]).getByRole("button"));
    expect(onSelect).toHaveBeenCalledWith("star_align");
  });
});
