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
  name, value, via: "ext", tier, reason: `because ${name}`, axis_reason: "", premise: [], because: "",
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
  it("puts what could need you first, and folds what is finished", async () => {
    // `impl-settled`: *no-rule values first as CHOICES, then measured with its premise, then
    // 'n settled' folded. Never alphabetical.*
    //
    // **This is a different claim from the four tier groups it replaced.** Four equal `<details>`
    // said *here are your parameters, by category*; three bands say *this many need you, this
    // many were measured, the rest are done* — which is the question the card exists to answer.
    show(STEP);
    await screen.findByTestId("band-needs-you");

    const order = Array.from(
      document.querySelectorAll(
        '[data-testid="band-needs-you"], [data-testid="band-measured"], [data-testid="show-settled"]',
      ),
    ).map((el) => el.getAttribute("data-testid"));

    expect(order).toEqual(["band-needs-you", "band-measured", "show-settled"]);
  });

  it("names the two open bands with the API's words, never its own", async () => {
    // The vocabulary was hardcoded here once and the operator caught it: nothing in the
    // repository agreed that tier 2 should be called `Standard practice`. `useTiers` is the one
    // declaration, and the card falls back to the number rather than inventing a word.
    show(STEP);
    await waitFor(() =>
      expect(screen.getByTestId("band-needs-you").textContent).toContain("Needs your decision"),
    );
    expect(screen.getByTestId("band-measured").textContent).toContain("Check the premise");
  });

  it("counts each band beside its name", async () => {
    show(STEP);
    expect(await screen.findByTestId("band-needs-you")).toHaveTextContent("· 1");
    expect(screen.getByTestId("show-settled")).toHaveTextContent("1 settled");
  });

  it("keeps the settled band shut until it is asked for", () => {
    // The whole point of the fold: most settings need no attention, and the card says so
    // without hiding them. A card that opened everything would bury the two that matter.
    show(STEP);
    expect(screen.queryByTestId("band-settled")).toBeNull();
    fireEvent.click(screen.getByTestId("show-settled"));
    expect(screen.getByTestId("band-settled")).toBeInTheDocument();
  });

  it("shows an undecided value as an absence, not as an empty field", () => {
    // A tier-4 setting has no value because nobody decided one. Rendering "" would read as
    // decided, to nothing.
    show(STEP);
    const undecided = screen.getAllByTestId("setting").find((s) => s.dataset.tier === "4")!;
    expect(undecided.textContent).toContain("—");
  });

  it("offers no control where the card is a record rather than a draft", () => {
    // **The premise of this test changed and the rule did not.** It read "read-only until a
    // pipeline has somewhere to be saved" — 3C's argument that a box which looks typeable and
    // discards what you type is worse than a value that says it is a record. `DraftParam` is
    // now somewhere to put the answer, so the card is editable WHEN GIVEN `onSet` and still
    // offers nothing when not.
    show(STEP);
    expect(document.querySelectorAll("input, select")).toHaveLength(0);
    expect(screen.queryByTestId("setting-choice")).toBeNull();
    expect(screen.getByText(/read-only: this pipeline is a record/i)).toBeTruthy();
  });
});

describe("answering a parameter", () => {
  const enumSetting = {
    name: "index_format", value: "bai", via: "ext", tier: 4,
    reason: "no rule matched", axis_reason: "", premise: [],
    because: "every downstream tool reads BAI",
    domain: { kind: "enum", values: ["bai", "csi"], minimum: null, maximum: null },
  };
  const freeSetting = {
    name: "seq_platform", value: null, via: "ext", tier: 4,
    reason: "no rule matched", axis_reason: "", premise: [], because: "",
    domain: null,
  };
  const boolSetting = {
    name: "star_ignore_sjdbgtf", value: null, via: "ext", tier: 2,
    reason: "align with the annotation", axis_reason: "", premise: [], because: "",
    domain: { kind: "boolean", values: [], minimum: null, maximum: null },
  };
  const numberSetting = {
    name: "read_length", value: null, via: "meta", tier: 4,
    reason: "no rule matched", axis_reason: "", premise: [], because: "",
    domain: { kind: "integer", values: [], minimum: null, maximum: null },
  };
  const step = (settings: unknown[]) =>
    ({ id: "sort", process: "SAMTOOLS_SORT", contract_id: "nf-core/samtools/sort@1.21.0",
       tier: 2, reason: "", ports: [], settings }) as never;

  it("renders CHOICES, not a dropdown, where the contract enumerates", () => {
    // `impl-settled`: *no-rule values first as CHOICES not a text field*. A `<select>` hides
    // the alternatives behind a click, which on the one band a person is meant to act on is
    // exactly the wrong way round — you cannot see what you are choosing between until you
    // have already engaged with the control.
    show(step([enumSetting]), () => {});
    expect(document.querySelector("select")).toBeNull();
    expect(screen.getAllByTestId("setting-choice").map((c) => c.textContent)).toEqual(
      ["bai", "csi"],
    );
  });

  it("marks the chosen chip rather than leaving the row ambiguous", () => {
    show(step([enumSetting]), () => {});
    const on = screen.getAllByTestId("setting-choice").filter((c) => c.dataset.on);
    expect(on.map((c) => c.textContent)).toEqual(["bai"]);
  });

  it("renders a free input where the contract declares no domain", () => {
    // seq_platform declares none deliberately: the list of sequencing platforms is open, and a
    // param whose legal values cannot be enumerated declares none. Three invented chips there
    // would be a closed vocabulary the registry never wrote.
    show(step([freeSetting]), () => {});
    expect(screen.getByTestId("setting-field").tagName).toBe("INPUT");
    expect(screen.queryByTestId("setting-choice")).toBeNull();
  });

  it("reports a chosen value by name", () => {
    const set = vi.fn();
    show(step([enumSetting]), set);
    fireEvent.click(screen.getAllByTestId("setting-choice")[1]);
    expect(set).toHaveBeenCalledWith("index_format", "csi");
  });

  it("clicking the chosen chip hands it back to the resolver", () => {
    // Taking an answer back has to be possible. The `<select>` did it with a blank option in a
    // list of legal values — which read as a legal value.
    const set = vi.fn();
    show(step([enumSetting]), set);
    fireEvent.click(screen.getAllByTestId("setting-choice")[0]);
    expect(set).toHaveBeenCalledWith("index_format", null);
  });

  it("clearing a free input hands it back too", () => {
    const set = vi.fn();
    show(step([{ ...freeSetting, value: "illumina" }]), set);
    fireEvent.change(screen.getByTestId("setting-field"), { target: { value: "" } });
    expect(set).toHaveBeenCalledWith("seq_platform", null);
  });

  it("keeps the convention visible after you depart from it", () => {
    // `reason` becomes YOUR reason the moment you answer; `because` is the contract author's
    // note on the default and survives, so the thing you overrode is still readable.
    show(step([enumSetting]), () => {});
    expect(screen.getByTestId("setting-because")).toHaveTextContent("every downstream tool");
  });

  it("marks a boolean the resolver spelled its own way", () => {
    // **`SettingView.value` is rendered for display and `Domain` declares the words.** A
    // boolean comes back as Python's `False` and the domain's members are `true` / `false`, so
    // an exact comparison marks nothing and every settled boolean reads as unanswered.
    show(step([{ ...boolSetting, value: "False" }]), () => {});
    fireEvent.click(screen.getByTestId("show-settled"));
    const on = screen.getAllByTestId("setting-choice").filter((c) => c.dataset.on);
    expect(on.map((c) => c.textContent)).toEqual(["false"]);
  });

  it("sends a boolean, not the string 'true'", () => {
    // `Domain.refuse` accepts a boolean domain only when the value IS a bool. The `<select>`
    // this replaced sent a string, which is a shape the contract would refuse — and a chip is
    // one click from doing the same.
    const set = vi.fn();
    show(step([{ ...boolSetting, value: "False" }]), set);
    fireEvent.click(screen.getByTestId("show-settled"));
    fireEvent.click(screen.getAllByTestId("setting-choice")[0]);
    expect(set).toHaveBeenCalledWith("star_ignore_sjdbgtf", true);
  });

  it("sends a number where the domain is numeric", () => {
    const set = vi.fn();
    show(step([numberSetting]), set);
    fireEvent.change(screen.getByTestId("setting-field"), { target: { value: "12" } });
    expect(set).toHaveBeenCalledWith("read_length", 12);
  });

  it("stops calling a value undecided once you have decided it", () => {
    // **Invariant 6 is not *hide it once somebody answers*.** A tier-4 value keeps its tier for
    // good, so the band stays and the row stays in it — what changes is the sentence over it,
    // because *needs your decision* is false about a decision that has been made. The status
    // line was making that claim about five values on a pipeline where you had answered two.
    show(step([{ ...enumSetting, answered: true }]), () => {});
    const band = screen.getByTestId("band-needs-you");
    expect(band.textContent).toContain("Answered by you · 1");
    expect(band.textContent).not.toContain("Needs your decision");
    expect(screen.getByTestId("setting-yours")).toBeInTheDocument();
  });

  it("keeps the row where it was while you are typing into it", async () => {
    // **A control must not migrate out from under the cursor using it.** Answered values were
    // briefly given a band of their own; typing one character marked the value answered, the
    // row moved, React unmounted the input, and `ILLUMINA` left `I` behind. One band, and the
    // heading is what moves.
    const mixed = [{ ...enumSetting, answered: true }, { ...freeSetting, name: "other" }];
    show(step(mixed), () => {});
    const band = await screen.findByTestId("band-needs-you");
    await waitFor(() => expect(band.textContent).toContain("Needs your decision"));
    expect(band.querySelectorAll('[data-testid="setting"]')).toHaveLength(2);
    expect(band.textContent).toContain("Needs your decision · 1");
  });

  it("keeps a settled value answerable once the band is open", () => {
    // **Folded is not read-only.** Departing from a convention is a thing a person is allowed
    // to do — and a settled band that only displayed would make `because`, which exists to keep
    // the departed-from convention visible, describe something nobody could reach.
    const set = vi.fn();
    show(step([{ ...enumSetting, tier: 2, reason: "BAI, not CSI" }]), set);
    fireEvent.click(screen.getByTestId("show-settled"));
    fireEvent.click(screen.getAllByTestId("setting-choice")[1]);
    expect(set).toHaveBeenCalledWith("index_format", "csi");
  });
});
