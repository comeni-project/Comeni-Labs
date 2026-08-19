import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";

const setting = (name: string, tier: number, value: string | null) => ({
  name, value, via: "ext", tier, reason: `because ${name}`, axis_reason: "",
});

const STEP = {
  id: "star_align",
  process: "STAR_ALIGN",
  contract_id: "nf-core/star/align@1.11.0",
  tier: 3,
  reason: "a rule matched",
  ports: [],
  settings: [
    setting("seq_platform", 4, null),
    setting("star_ignore_sjdbgtf", 2, "False"),
    setting("read_length", 3, "150"),
  ],
};

describe("the settings card", () => {
  it("groups by how each was decided, worst first", () => {
    render(<Settings step={STEP} onClose={vi.fn()} />);
    const groups = Array.from(document.querySelectorAll("details"));
    expect(groups.map((g) => g.querySelector("summary")!.textContent!.trim())).toEqual([
      "Needs your decision 1",
      "Check the premise 1",
      "Standard practice 1",
    ]);
  });

  it("opens the two that need a person and collapses the two that do not", () => {
    // `dashboard.md` §5 — the collapsed groups are the point: most settings need no attention,
    // and the card says so without hiding them.
    render(<Settings step={STEP} onClose={vi.fn()} />);
    const groups = Array.from(document.querySelectorAll("details"));
    expect(groups[0].open).toBe(true);
    expect(groups[1].open).toBe(true);
    expect(groups[2].open).toBe(false);
  });

  it("shows an undecided value as an absence, not as an empty field", () => {
    // A tier-4 setting has no value because nobody decided one. Rendering "" would read as
    // decided, to nothing.
    render(<Settings step={STEP} onClose={vi.fn()} />);
    const undecided = screen.getAllByTestId("setting").find((s) => s.dataset.tier === "4")!;
    expect(undecided.textContent).toContain("—");
  });

  it("says it is read-only rather than offering a field that discards what you type", () => {
    render(<Settings step={STEP} onClose={vi.fn()} />);
    expect(document.querySelectorAll("input, select")).toHaveLength(0);
    expect(screen.getByText(/read-only until a pipeline has somewhere to be saved/i)).toBeTruthy();
  });
});
