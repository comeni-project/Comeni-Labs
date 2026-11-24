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
  { id: "featurecounts", process: "SUBREAD_FEATURECOUNTS", contract_id: "nf-core/subread/featurecounts@2.1.1",
    runs: "per_item", tier: 4, reason: "", ports: [], settings: [
      setting("strandedness", 4, null, "Not in your description, and not measured."),
    ] },
  { id: "multiqc", process: "MULTIQC", contract_id: "nf-core/multiqc@1.21", runs: "once", tier: 1, reason: "",
    ports: [], settings: [] },
] as unknown as AnsweredStep[];

/** The file as the server writes it (the v8 layout `fileLines` reads). */
const READY: AuthoringPreview = { revision: 4, state: "ready", findings: [], text: [
  "version: 9", "steps:",
  "- id: star_align", "  settings:",
  "  - name: sjdbOverhang", "    value: '150'", "    why:", "      tier: 3",
  "  - name: twopassMode", "    value: None", "    why:", "      tier: 2",
  "- id: featurecounts", "  settings:",
  "  - name: strandedness", "    value: null", "    why:", "      tier: 4",
  "- id: multiqc", "  settings: []", "gate: null", ""].join("\n") };

let emitted: { ok: boolean; status: number; body: unknown } = { ok: true, status: 200,
  body: { revision: 4, main_nf: "workflow {\n  STAR_ALIGN()\n}\n", nextflow_config: "docker.enabled = true\n" } };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/registry/tiers")
    ? { ok: true, status: 200, json: async () => TIERS }
    : url.includes("/emitted")
      ? { ok: emitted.ok, status: emitted.status, json: async () => emitted.body }
      : { ok: false, status: 404, json: async () => ({ detail: "not here" }) })));
});
afterEach(() => vi.unstubAllGlobals());

function file(overrides: Partial<Parameters<typeof PipelineFile>[0]> = {}) {
  const props = { steps: STEPS, preview: READY, draftId: "d1", kept: false, onChange: vi.fn(), onAsk: vi.fn(),
    onSay: vi.fn(), ...overrides };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PipelineFile {...props} />
    </QueryClientProvider>,
  );
  return props;
}

const line = (text: string) =>
  within(screen.getByTestId("artifact-text")).getAllByTestId("file-line").find((l) => l.textContent?.startsWith(text))!;

describe("the file first, every value marked (one builder plan 5, issue 394)", () => {
  it("counts how the values were decided, each count a filter, in the outline", () => {
    file();
    const outline = screen.getByRole("navigation", { name: "outline of the file" });
    const strip = within(outline).getByRole("group", { name: "how the values were decided" });
    expect(within(strip).getAllByRole("button").map((b) => b.textContent)).toEqual(
      ["1 settled", "1 measured", "1 needs you"]);
  });

  it("marks each setting's first line with how it was decided", async () => {
    file();
    expect(await within(line("  - name: sjdbOverhang")).findByText("measured")).toBeInTheDocument();
    expect(within(line("  - name: strandedness")).getByText("needs you")).toBeInTheDocument();
    expect(within(line("    value: '150'")).queryByText("measured")).toBeNull();
  });

  it("filters the file to one kind, keeping each step's line, and shows all again", () => {
    file();
    fireEvent.click(screen.getByRole("button", { name: "1 measured" }));
    const shown = within(screen.getByTestId("artifact-text")).getAllByTestId("file-line").map((l) => l.textContent);
    expect(shown.some((t) => t?.startsWith("  - name: sjdbOverhang"))).toBe(true);
    expect(shown.some((t) => t?.startsWith("  - name: twopassMode"))).toBe(false);
    expect(shown.some((t) => t?.startsWith("  - name: strandedness"))).toBe(false);
    expect(shown).toContain("- id: featurecounts");
    expect(screen.getByText(/showing measured/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "show all" }));
    expect(line("  - name: strandedness")).toBeTruthy();
  });

  it("opens a value's reason beneath its lines, with Ask the AI and Change (issue 499)", async () => {
    const p = file();
    fireEvent.click(line("      tier: 3"));
    const reason = screen.getByRole("region", { name: "the reason" });
    expect(reason).toHaveTextContent("150");
    expect(reason).toHaveTextContent("Read length minus one.");
    expect(reason).toHaveTextContent("read_length = 151");
    expect(await within(reason).findByText("measured")).toBeInTheDocument();
    // Beneath the value's last line, before the next setting's first.
    const lines = within(screen.getByTestId("artifact-text")).getAllByTestId("file-line");
    const twopass = lines.find((l) => l.textContent?.startsWith("  - name: twopassMode"))!;
    expect(reason.compareDocumentPosition(twopass) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(within(reason).getByRole("button", { name: "Change" }));
    expect(p.onChange).toHaveBeenCalledWith("star_align");
    fireEvent.click(within(reason).getByRole("button", { name: "Ask the AI" }));
    expect(p.onAsk).toHaveBeenCalledWith("About STAR_ALIGN sjdbOverhang: ");
  });

  it("tints only an open value's own line, never every null (walk 2026-11-15)", () => {
    file({ preview: { ...READY, text: READY.text.replace("gate: null", "gate: null\nemitted: null") } });
    const tinted = within(screen.getByTestId("artifact-text")).getAllByTestId("file-line")
      .filter((l) => l.dataset.open).map((l) => l.textContent);
    expect(tinted).toEqual(["    value: null"]);
  });

  it("has no column waiting for a click (issue 495)", () => {
    file();
    expect(screen.queryByText(/Click a value/)).toBeNull();
    expect(screen.queryByRole("complementary", { name: "the reason" })).toBeNull();
  });
});

describe("the Nextflow it compiles to", () => {
  it("compiles main.nf and nextflow.config on first open", async () => {
    file();
    fireEvent.click(screen.getByRole("tab", { name: "main.nf" }));
    expect(await screen.findByText(/STAR_ALIGN\(\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "nextflow.config" }));
    expect(await screen.findByText(/docker.enabled = true/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compile again" })).toBeInTheDocument();
    const asked = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls
      .filter(([url]) => url.includes("/emitted"));
    expect(asked).toHaveLength(1);
  });

  it("says why when there is nothing to compile yet", async () => {
    emitted = { ok: false, status: 422, body: { detail: "MI0219: there is no pipeline to compile yet: empty" } };
    file();
    fireEvent.click(screen.getByRole("tab", { name: "main.nf" }));
    expect(await screen.findByText(/there is no pipeline to compile yet/)).toBeInTheDocument();
    emitted = { ok: true, status: 200,
      body: { revision: 4, main_nf: "workflow {\n  STAR_ALIGN()\n}\n", nextflow_config: "docker.enabled = true\n" } };
  });
});

describe("the file itself", () => {
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
  });

  it("draws the kept file's tab once there is one", () => {
    file({ kept: true });
    expect(screen.getByRole("tab", { name: "as kept" })).toBeEnabled();
  });

  it("offers the kept pipeline as a zip and its decisions report, once it is kept (issue 619)", () => {
    file({ kept: true });
    const zip = screen.getByRole("link", { name: "Download the kept pipeline as a zip" });
    expect(zip).toHaveAttribute("href", "/api/pipeline/drafts/d1/bundle");
    expect(zip).toHaveAttribute("download");
    const report = screen.getByRole("link", { name: "Open the decisions report" });
    expect(report).toHaveAttribute("href", "/api/pipeline/drafts/d1/decisions");
    expect(report).toHaveAttribute("target", "_blank");
  });

  it("offers neither before the pipeline is kept", () => {
    file();
    expect(screen.queryByRole("link", { name: "Download the kept pipeline as a zip" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Open the decisions report" })).toBeNull();
  });

  it("says why there is no file when the preview is outdated", () => {
    file({ preview: { revision: 4, state: "outdated", text: "", findings: [] } });
    expect(screen.getByTestId("preview-outdated")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download pipeline.yml" })).toBeDisabled();
  });
});

describe("the outline (issue 499)", () => {
  it("lists the file's sections and its steps with their state, and takes the file to each", () => {
    file();
    const outline = screen.getByRole("navigation", { name: "outline of the file" });
    expect(within(outline).getByRole("button", { name: /^Steps/ })).toHaveTextContent("3");
    const steps = within(outline).getAllByRole("button", { name: /^step / });
    expect(steps.map((b) => b.getAttribute("aria-label"))).toEqual([
      "step star_align, measured", "step featurecounts, needs you", "step multiqc, settled"]);
    const gate = line("gate: null");
    gate.scrollIntoView = vi.fn();
    fireEvent.click(within(outline).getByRole("button", { name: "Checks" }));
    expect(gate.scrollIntoView).toHaveBeenCalled();
    const counts = line("- id: featurecounts");
    counts.scrollIntoView = vi.fn();
    fireEvent.click(steps[1]);
    expect(counts.scrollIntoView).toHaveBeenCalled();
  });

  it("opens on the step it was asked to show", () => {
    const counts = vi.fn();
    Element.prototype.scrollIntoView = counts;
    file({ focusStep: "featurecounts" });
    expect(counts).toHaveBeenCalled();
  });
});

const FOLDED: AuthoringPreview = { revision: 4, state: "ready", findings: [], text: [
  "steps:", "- id: star_align", "  module:", "    contract_id: nf-core/star/align@2.7.11a",
  "    digest: sha256:abc", "  settings:", "  - name: sjdbOverhang", "    value: '150'", ""].join("\n") };

describe("folding (issue 499)", () => {
  it("folds a step's module to one summary line, and opens it", () => {
    file({ preview: FOLDED });
    expect(screen.queryByText(/digest: sha256:abc/)).toBeNull();
    const fold = screen.getByRole("button", { name: /\{ nf-core\/star\/align@2.7.11a · 3 lines \}/ });
    fireEvent.click(fold);
    expect(screen.getByText(/digest: sha256:abc/)).toBeInTheDocument();
  });
});

describe("asking about what is selected (issue 499)", () => {
  it("offers Explain this for selected lines, and asks with their real line numbers", () => {
    const p = file();
    const from = line("  - name: sjdbOverhang");
    const to = line("    value: '150'");
    const range = document.createRange();
    // Within each line's own text (its number and fold arrow are drawn by CSS).
    range.setStart(from.children[2].firstChild!, 0);
    range.setEnd(to.children[2].firstChild!, 4);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.mouseUp(screen.getByTestId("artifact-text"));
    const bar = screen.getByRole("toolbar", { name: "about the selection" });
    fireEvent.click(within(bar).getByRole("button", { name: "Explain this" }));
    // Which step and setting the lines are in (walk 2026-11-15): the agent cannot see the file.
    expect(p.onSay).toHaveBeenCalledWith(expect.stringMatching(/^About lines 5–6 of pipeline\.yml \(step star_align, setting sjdbOverhang\):\n> {3}- name: sjdbOverhang\n> {5}value: '150'\nExplain this\.$/));
  });
});

describe("the AI beside the file (issue 499)", () => {
  it("is the builder's conversation, and folds away", () => {
    file({ aside: <div>the thread</div> });
    const panel = screen.getByRole("region", { name: "Ask about this pipeline" });
    expect(panel).toHaveTextContent("the thread");
    fireEvent.click(screen.getByRole("button", { name: "Hide the AI panel" }));
    expect(screen.queryByRole("region", { name: "Ask about this pipeline" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show the AI panel" }));
    expect(screen.getByRole("region", { name: "Ask about this pipeline" })).toBeInTheDocument();
  });
});
