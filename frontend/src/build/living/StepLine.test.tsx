import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { StepLine } from "./StepLine";

function line(session: AuthoringSession = FAKE_SESSION, selected: string | null = null) {
  const onSelect = vi.fn();
  render(<StepLine session={session} steps={FAKE_STEPS} selected={selected} onSelect={onSelect} />);
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

  it("names the steps still to come with their place in the plan, drawn as not reached", () => {
    const { rows } = line();
    expect(rows[5]).toHaveTextContent(/SUBREAD_FEATURECOUNTS.*step 5/);
    expect(rows[5].getAttribute("data-dot")).toBe("later");
    expect(within(rows[5]).queryByRole("button")).toBeNull();
  });

  it("says a step's place as the boards do, without the plan's length", () => {
    const { rows } = line();
    expect(rows[1]).toHaveTextContent(/step 1/);
    expect(rows[1]).not.toHaveTextContent(/of 5/);
  });

  it("rings a step with measured values in the measured colour and says how many, beside who chose", () => {
    const { rows } = line();
    expect(rows[3].getAttribute("data-dot")).toBe("measured");
    expect(rows[3]).toHaveTextContent(/you chose · 1 measured$/);
    expect(rows[2].getAttribute("data-dot")).toBe("done");
  });

  it("draws the line as reached up to the step on offer, and not reached after it", () => {
    const { rows } = line();
    expect(rows.slice(1, 5).map((r) => r.getAttribute("data-line"))).toEqual(["reached", "reached", "reached", "reached"]);
    expect(rows[5].getAttribute("data-line")).toBe("later");
    expect(rows[4].getAttribute("data-dot")).toBe("now");
  });

  it("says nothing of steps to come when nothing is on offer", () => {
    const { rows } = line({ ...FAKE_SESSION, pending_proposal: null,
      progress: { reviewed: 5, total: 5, active: null } } as AuthoringSession);
    expect(rows.map((r) => r.getAttribute("data-dot"))).not.toContain("later");
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
