import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Settings } from "./Settings";

/** **The card reads the tier vocabulary from the API now**, so it needs a client — the group
 *  headings were typed into this file until the operator pointed out that nothing in the
 *  repository agreed they should say that. */
const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "pea-soft" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

function show(step: Parameters<typeof Settings>[0]["step"]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => TIERS }),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <Settings step={step} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

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
  it("groups by how each was decided, worst first", async () => {
    // **Awaited, because the names arrive from the API now.** Until they do the card shows
    // `tier 4` rather than inventing a word — an interface that guesses when the vocabulary has
    // not loaded is how the hardcoding started.
    show(STEP);
    await waitFor(() =>
      expect(document.querySelector("summary")!.textContent).toContain("Needs your decision"),
    );
    const groups = Array.from(document.querySelectorAll("details"));
    expect(groups.map((g) => g.querySelector("summary")!.textContent!.trim())).toEqual([
      "Needs your decision 1",
      "Check the premise 1",
      "Standard practice 1",
    ]);
  });

  it("opens the two that need a person and collapses the two that do not", async () => {
    // `dashboard.md` §5 — the collapsed groups are the point: most settings need no attention,
    // and the card says so without hiding them.
    show(STEP);
    const groups = Array.from(document.querySelectorAll("details"));
    expect(groups[0].open).toBe(true);
    expect(groups[1].open).toBe(true);
    expect(groups[2].open).toBe(false);
  });

  it("shows an undecided value as an absence, not as an empty field", () => {
    // A tier-4 setting has no value because nobody decided one. Rendering "" would read as
    // decided, to nothing.
    show(STEP);
    const undecided = screen.getAllByTestId("setting").find((s) => s.dataset.tier === "4")!;
    expect(undecided.textContent).toContain("—");
  });

  it("says it is read-only rather than offering a field that discards what you type", () => {
    show(STEP);
    expect(document.querySelectorAll("input, select")).toHaveLength(0);
    expect(screen.getByText(/read-only until a pipeline has somewhere to be saved/i)).toBeTruthy();
  });
});
