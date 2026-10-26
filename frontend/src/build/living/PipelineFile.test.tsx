import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthoringPreview } from "../../api/types";
import type { AnsweredStep } from "../useBuilder";
import { PipelineFile } from "./PipelineFile";

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "line-2" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "needs-you" },
];

const setting = (name: string, tier: number, value: string | null, reason: string, premise: string[] = [],
                 answered = false) =>
  ({ name, value, via: "ext", tier, reason, because: "", axis_reason: "", optional: false, premise, answered });

const STEPS = [
  { id: "star_align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@2.7.11a", runs: "per_item",
    tier: 3, reason: "", ports: [], settings: [
      { ...setting("sjdbOverhang", 3, "150", "Read length minus one.", ["read_length = 151"]), evidence: "measured" },
      setting("twopassMode", 2, "None", "nf-core's default for this module."),
    ] },
  { id: "featurecounts", process: "SUBREAD_FEATURECOUNTS", contract_id: "nf-core/subread/featurecounts@2.0.6",
    runs: "per_item", tier: 4, reason: "", ports: [], settings: [
      setting("strandedness", 4, null, "Not in your description, and not measured."),
    ] },
  { id: "multiqc", process: "MULTIQC", contract_id: "nf-core/multiqc@1.21", runs: "once", tier: 1, reason: "",
    ports: [], settings: [] },
] as unknown as AnsweredStep[];

const READY: AuthoringPreview = { revision: 4, state: "ready", findings: [],
  text: "steps:\n  - id: featurecounts\n    settings:\n      strandedness:\n        value: null\n" };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/registry/tiers")
    ? { ok: true, status: 200, json: async () => TIERS }
    : { ok: false, status: 404, json: async () => ({ detail: "not here" }) })));
});
afterEach(() => vi.unstubAllGlobals());

function file(overrides: Partial<Parameters<typeof PipelineFile>[0]> = {}) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PipelineFile steps={STEPS} preview={READY} draftId="d1" kept={false} {...overrides} />
    </QueryClientProvider>,
  );
}

describe("every value and its reason", () => {
  it("counts the values and how each was decided", () => {
    file();
    const summary = screen.getByRole("region", { name: "how the values were decided" });
    expect(summary).toHaveTextContent("3 values, and how each was decided");
    expect(summary).toHaveTextContent("1 settled by a rule, a convention or you");
    expect(summary).toHaveTextContent("1 measured from your files");
    expect(summary).toHaveTextContent("1 needs you");
  });

  it("says nothing needs the person, quietly, when nothing does", () => {
    file({ steps: STEPS.slice(0, 1) });
    const summary = screen.getByRole("region", { name: "how the values were decided" });
    expect(summary).toHaveTextContent("nothing needs you");
    expect(within(summary).getByText("nothing needs you").className).not.toContain("needs-you");
  });

  it("gives each setting its value, how it was decided and why, with the premise", async () => {
    file();
    const table = screen.getByRole("table", { name: "STAR_ALIGN settings" });
    const row = within(table).getByRole("row", { name: /sjdbOverhang/ });
    expect(row).toHaveTextContent("150");
    expect(await within(row).findByText("measured")).toBeInTheDocument();
    expect(row).toHaveTextContent("Read length minus one.");
    expect(row).toHaveTextContent("read_length = 151");
  });

  it("does not call a rule's value measured when what it read was typed (issue 397)", async () => {
    const typed = { ...setting("sjdbOverhang", 3, "149", "Read length minus one.",
                               ["read_length is 150, asserted, not measured"]), evidence: "not_measured" };
    file({ steps: [{ ...STEPS[0], settings: [typed] }] as AnsweredStep[] });
    const row = screen.getByRole("row", { name: /sjdbOverhang/ });
    expect(await within(row).findByText("check the premise")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "how the values were decided" }))
      .toHaveTextContent("0 measured from your files");
  });

  it("shows an open value as null, marked as needing the person", async () => {
    file();
    const row = within(screen.getByRole("table", { name: "SUBREAD_FEATURECOUNTS settings" }))
      .getByRole("row", { name: /strandedness/ });
    expect(row).toHaveTextContent("null");
    expect(within(row).getByText("needs you")).toBeInTheDocument();
  });

  it("marks an optional open value as optional, counts it apart, and keeps it among the open (issue 384)", () => {
    const optional = { ...setting("seq_platform", 4, null, "nothing decided it"), optional: true };
    file({ steps: [{ ...STEPS[0], settings: [...STEPS[0].settings, optional] }] as AnsweredStep[] });
    const row = screen.getByRole("row", { name: /seq_platform/ });
    expect(within(row).getByText("optional")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "how the values were decided" })).toHaveTextContent("1 optional");
    fireEvent.click(screen.getByRole("button", { name: "Show only open" }));
    expect(screen.getByRole("row", { name: /seq_platform/ })).toBeInTheDocument();
  });

  it("says a step with nothing to set has nothing to set", () => {
    file();
    expect(screen.getByRole("region", { name: "MULTIQC" })).toHaveTextContent("Nothing to set");
  });

  it("can show only the open values, and says when none are", () => {
    file();
    fireEvent.click(screen.getByRole("button", { name: "Show only open" }));
    expect(screen.queryByRole("row", { name: /sjdbOverhang/ })).toBeNull();
    expect(screen.getByRole("row", { name: /strandedness/ })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "MULTIQC" })).toBeNull();
  });

  it("says nothing is open when every value is decided", () => {
    file({ steps: STEPS.slice(0, 1) });
    fireEvent.click(screen.getByRole("button", { name: "Show only open" }));
    expect(screen.getByText("Nothing is open.")).toBeInTheDocument();
  });
});

describe("the file itself", () => {
  it("is drawn line by line, and a null line is marked", () => {
    file();
    const text = screen.getByTestId("artifact-text");
    const lines = within(text).getAllByTestId("file-line");
    expect(lines.length).toBeGreaterThan(0);
    const marked = lines.filter((line) => line.getAttribute("data-open") === "true");
    expect(marked.map((line) => line.textContent)).toEqual(["        value: null"]);
  });

  it("can be downloaded as the text on screen", async () => {
    const created: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => { created.push(blob); return "blob:x"; });
    URL.revokeObjectURL = vi.fn();
    file();
    fireEvent.click(screen.getByRole("button", { name: "Download pipeline.yml" }));
    expect(created.length).toBe(1);
    expect(await created[0].text()).toBe(READY.text);
  });

  it("names the file as the board does, and offers the kept one only once the pipeline is kept", () => {
    file();
    expect(screen.getByRole("tab", { name: "pipeline.yml" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("tab", { name: "as kept" })).toBeNull();
    expect(screen.getByText("same file you download")).toBeInTheDocument();
  });

  it("draws the kept file's tab once there is one", () => {
    file({ kept: true });
    expect(screen.getByRole("tab", { name: "as kept" })).toBeEnabled();
  });

  it("says why there is no file when the preview is outdated, and still lists the values", () => {
    file({ preview: { revision: 4, state: "outdated", text: "", findings: [] } });
    expect(screen.getByTestId("preview-outdated")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "STAR_ALIGN settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download pipeline.yml" })).toBeDisabled();
  });
});


describe("the file's sections", () => {
  const WHOLE: AuthoringPreview = { revision: 4, state: "ready", findings: [],
    text: "version: 6\nintent:\n  want: [counts.matrix]\nsteps:\n  - id: star_align\ngate:\n  passed: true\n" };

  it("offers a chip for each section the file has, with the table's own marked as shown", () => {
    file({ preview: WHOLE });
    const chips = within(screen.getByRole("navigation", { name: "sections of the file" })).getAllByRole("button");
    expect(chips.map((c) => c.textContent)).toEqual(["Goal", "Steps 3", "Settings 3", "Checks"]);
    expect(screen.getByRole("button", { name: "Settings 3" })).toHaveAttribute("aria-current", "true");
  });

  it("takes the file to a section's first line", () => {
    file({ preview: WHOLE });
    const lines = within(screen.getByTestId("artifact-text")).getAllByTestId("file-line");
    const intent = lines.find((line) => line.textContent === "intent:")!;
    intent.scrollIntoView = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Goal" }));
    expect(intent.scrollIntoView).toHaveBeenCalled();
  });

  it("says every value has a reason, or is marked open", () => {
    file();
    expect(screen.getByText("Every value has a reason, or it is marked open.")).toBeInTheDocument();
  });
});
