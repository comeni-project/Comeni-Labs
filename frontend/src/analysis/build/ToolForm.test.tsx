import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { AnsweredStep } from "../../build/useBuilder";
import { ToolForm } from "./ToolForm";

const setting = (name: string, extra: Record<string, unknown> = {}) => ({
  name, value: null, via: "ext", tier: 2, reason: "", because: "", axis_reason: "", optional: false,
  premise: [], ...extra,
});

const STEP = {
  id: "star_align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@2.7.11b", tier: 3,
  runs: "per_item", reason: "", checked_per_sample: [], takes_samples: null, parts: null,
  ports: [
    { name: "reads", type_id: "fastq.reads", side: "in", accepts: [], optional: false, adds: [], met: true, states: [], gathers: false },
    { name: "index", type_id: "genome.index.star", side: "in", accepts: [], optional: false, adds: [], met: true, states: [], gathers: false },
    { name: "bam", type_id: "alignment.bam", side: "out", accepts: [], optional: false, adds: [], met: true, states: [], gathers: false },
  ],
  settings: [
    setting("strandedness", { tier: 4, domain: { kind: "enum", values: ["forward", "reverse", "unstranded"] },
                              reason: "No rule settles it." }),
    setting("sjdbOverhang", { tier: 3, value: "150", evidence: "measured", domain: { kind: "integer", values: [], minimum: 1, maximum: 1000 },
                              reason: "Read length is 151 bp, minus one." }),
    setting("twopassMode", { tier: 2, value: "false", domain: { kind: "boolean", values: [] }, reason: "Off by convention." }),
    setting("outSAMattrRGline", { tier: 2, value: "ID:x", domain: { kind: "string", values: [] }, reason: "One read group." }),
    setting("outFilterMultimapNmax", { tier: 1, value: "20", via: "args", answered: true,
                                        domain: { kind: "integer", values: [] }, reason: "" }),
  ],
} as unknown as AnsweredStep;

function form(over: Partial<Parameters<typeof ToolForm>[0]> = {}) {
  const props = {
    step: STEP, aiChoices: [], inputs: [
      { port: "reads", from: { data: "Samples", count: 24, href: "/a/d1/data/samples" } },
      { port: "index", from: { step: "STAR_GENOMEGENERATE" } },
    ],
    onSet: vi.fn(), onAsk: vi.fn(), onAccept: vi.fn(), ...over,
  };
  render(<MemoryRouter><ToolForm {...props} /></MemoryRouter>);
  return props;
}

describe("ToolForm", () => {
  it("tool form splits basic and advanced", () => {
    form();
    const basic = screen.getByRole("group", { name: "Basic" });
    // What needs the person, or was set by a person or the AI, is basic; what a rule settled is advanced.
    expect(within(basic).getByText("strandedness")).toBeTruthy();
    expect(within(basic).getByText("outFilterMultimapNmax")).toBeTruthy();
    expect(within(basic).queryByText("twopassMode")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Advanced/ }));
    const advanced = screen.getByRole("group", { name: "Advanced" });
    expect(within(advanced).getByText("twopassMode")).toBeTruthy();
    expect(within(advanced).getByText("sjdbOverhang")).toBeTruthy();
  });

  it("each control type renders from its setting kind", () => {
    form();
    fireEvent.click(screen.getByRole("button", { name: /Advanced/ }));
    expect(screen.getByRole("combobox", { name: "strandedness" })).toBeTruthy();
    const number = screen.getByRole("spinbutton", { name: "sjdbOverhang" }) as HTMLInputElement;
    expect(number.min).toBe("1");
    expect(number.max).toBe("1000");
    expect(screen.getByText("1–1000")).toBeTruthy();
    const yesNo = screen.getByRole("radiogroup", { name: "twopassMode" });
    expect(within(yesNo).getByRole("radio", { name: "No" }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("textbox", { name: "outSAMattrRGline" })).toBeTruthy();
  });

  it("a row carries its help, its source and Ask AI", () => {
    form();
    const row = screen.getByRole("group", { name: "Basic" }).querySelector('[data-setting="strandedness"]')!;
    expect(within(row as HTMLElement).getByText(/cannot run without it/)).toBeTruthy();
    expect(row.querySelector("[data-source]")?.getAttribute("data-source")).toBe("not_set");
    fireEvent.click(screen.getByRole("button", { name: /Advanced/ }));
    const measured = document.querySelector('[data-setting="sjdbOverhang"] [data-source]');
    expect(measured?.getAttribute("data-source")).toBe("measured");
    expect(document.querySelector('[data-setting="outFilterMultimapNmax"] [data-source]')?.getAttribute("data-source")).toBe("you");
  });

  it("changing a value sets it as the person's", () => {
    const props = form();
    fireEvent.change(screen.getByRole("combobox", { name: "strandedness" }), { target: { value: "reverse" } });
    expect(props.onSet).toHaveBeenCalledWith("strandedness", "reverse");
  });

  it("ask AI marks the suggested value AI until accepted", () => {
    const props = form({ aiChoices: [{ what: "set strandedness to reverse", because: "featureCounts said so" }] });
    const row = document.querySelector('[data-setting="strandedness"]') as HTMLElement;
    expect(row.querySelector("[data-source]")?.getAttribute("data-source")).toBe("ai");
    expect(within(row).getByText("featureCounts said so")).toBeTruthy();
    fireEvent.click(within(row).getByRole("button", { name: "Accept" }));
    expect(props.onAccept).toHaveBeenCalled();
    fireEvent.click(within(row).getByRole("button", { name: "Ask AI about strandedness" }));
    expect(props.onAsk).toHaveBeenCalledWith("strandedness");
  });

  it("a file setting shows its Data binding, never a path input", () => {
    form();
    const inputs = screen.getByRole("group", { name: "Inputs" });
    expect(within(inputs).getByText("reads")).toBeTruthy();
    expect(within(inputs).getByRole("link", { name: "Samples · 24" }).getAttribute("href")).toBe("/a/d1/data/samples");
    expect(within(inputs).getByText("from STAR_GENOMEGENERATE")).toBeTruthy();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(within(inputs).queryByRole("textbox")).toBeNull();
  });

  it("never shows the contract id", () => {
    form();
    expect(document.body.textContent).not.toContain("nf-core/star/align");
  });
});

describe("an open value, in plain words (issue 384)", () => {
  it("says why it is open, not the resolver's placeholder", () => {
    form({ step: { ...STEP, settings: [setting("index_format", {
      tier: 4, reason: "nothing decided 'index_format'; selected the first of 1 candidates without judgement — please review" })] } as AnsweredStep });
    expect(document.body.textContent).not.toMatch(/candidates without judgement/);
    expect(screen.getByText("No rule or answer decides this, and STAR_ALIGN cannot run without it.")).toBeTruthy();
  });

  it("says what an optional value does if it is left", () => {
    form({ step: { ...STEP, settings: [setting("seq_platform", { tier: 4, optional: true })] } as AnsweredStep });
    expect(screen.getByText("No rule or answer decides this. Left unset, STAR_ALIGN uses its tool's own default.")).toBeTruthy();
  });

  it("a typed value is sent once, when the field is left, never per keystroke", () => {
    const props = form();
    fireEvent.click(screen.getByRole("button", { name: /Advanced/ }));
    const box = screen.getByRole("textbox", { name: "outSAMattrRGline" });
    fireEvent.change(box, { target: { value: "ID:a" } });
    fireEvent.change(box, { target: { value: "ID:ab" } });
    expect(props.onSet).not.toHaveBeenCalled();
    fireEvent.blur(box);
    expect(props.onSet).toHaveBeenCalledExactlyOnceWith("outSAMattrRGline", "ID:ab");
  });
});
