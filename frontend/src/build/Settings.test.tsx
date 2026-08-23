import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function show(
  step: Parameters<typeof Settings>[0]["step"],
  onSet?: (name: string, value: string | null) => void,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => TIERS }),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <Settings step={step} onClose={vi.fn()} onSet={onSet} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const setting = (name: string, tier: number, value: string | null) => ({
  name, value, via: "ext", tier, reason: `because ${name}`, axis_reason: "", because: "",
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

  it("offers no field where the card is a record rather than a control", () => {
    // **The premise of this test changed and the rule did not.** It read "read-only until a
    // pipeline has somewhere to be saved" — 3C's argument that a box which looks typeable and
    // discards what you type is worse than a value that says it is a record. `DraftParam` is
    // now somewhere to put the answer, so the card is editable WHEN GIVEN `onSet` and still
    // offers nothing when not. The rule survives; only its default flipped.
    show(STEP);
    expect(document.querySelectorAll("input, select")).toHaveLength(0);
    expect(screen.getByText(/read-only: this pipeline is a record/i)).toBeTruthy();
  });
});

describe("tuning a parameter", () => {
  const enumSetting = {
    name: "index_format", value: "bai", via: "ext", tier: 2,
    reason: "BAI, not CSI", axis_reason: "", because: "every downstream tool reads BAI",
    domain: { kind: "enum", values: ["bai", "csi"], minimum: null, maximum: null },
  };
  const freeSetting = {
    name: "seq_platform", value: null, via: "ext", tier: 4,
    reason: "no rule matched", axis_reason: "", because: "",
    domain: null,
  };
  const step = (settings: unknown[]) =>
    ({ id: "sort", process: "SAMTOOLS_SORT", contract_id: "nf-core/samtools/sort@1.21.0",
       tier: 2, reason: "", ports: [], settings }) as never;

  it("renders a select where the contract declares a domain", () => {
    // dashboard.md §5: parameters with alternatives render as a <select>; free values as an
    // input. Without `domain` on the wire the browser cannot tell them apart, and index_format
    // — whose only legal values are bai and csi — was a text box.
    show(step([enumSetting]), () => {});
    const field = screen.getByTestId("setting-field");
    expect(field.tagName).toBe("SELECT");
    expect(Array.from(field.querySelectorAll("option")).map((o) => o.textContent)).toEqual(
      ["—", "bai", "csi"],
    );
  });

  it("renders a free input where the contract declares none", () => {
    // seq_platform declares no domain deliberately: the list of sequencing platforms is open,
    // and a param whose legal values cannot be enumerated declares none.
    show(step([freeSetting]), () => {});
    expect(screen.getByTestId("setting-field").tagName).toBe("INPUT");
  });

  it("reports a typed value by name", () => {
    const set = vi.fn();
    show(step([enumSetting]), set);
    fireEvent.change(screen.getByTestId("setting-field"), { target: { value: "csi" } });
    expect(set).toHaveBeenCalledWith("index_format", "csi");
  });

  it("clearing a value hands it back to the resolver rather than recording an empty answer", () => {
    const set = vi.fn();
    show(step([enumSetting]), set);
    fireEvent.change(screen.getByTestId("setting-field"), { target: { value: "" } });
    expect(set).toHaveBeenCalledWith("index_format", null);
  });

  it("keeps the convention visible after you depart from it", () => {
    // `reason` becomes YOUR reason the moment you type; `because` is the contract author's note
    // on the default and survives, so the thing you overrode is still readable.
    show(step([enumSetting]), () => {});
    expect(screen.getByTestId("setting-because")).toHaveTextContent("every downstream tool");
  });

  it("offers no field at all where the card is a record", () => {
    show(step([enumSetting]));
    expect(screen.queryByTestId("setting-field")).toBeNull();
    expect(screen.getByText(/Read-only: this pipeline is a record/)).toBeInTheDocument();
  });
});
