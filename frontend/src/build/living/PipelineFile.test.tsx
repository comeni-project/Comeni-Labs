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

/** The file as the server writes it (the v8 layout `fileLines` reads). */
const READY: AuthoringPreview = { revision: 4, state: "ready", findings: [], text: [
  "version: 8", "steps:",
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
    ...overrides };
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
  it("counts how the values were decided, each count a filter", () => {
    file();
    const strip = screen.getByRole("group", { name: "how the values were decided" });
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

  it("opens a value's reason beside the file from any of its lines", async () => {
    const p = file();
    fireEvent.click(line("      tier: 3"));
    const reason = screen.getByRole("complementary", { name: "the reason" });
    expect(reason).toHaveTextContent("STAR_ALIGN");
    expect(reason).toHaveTextContent("sjdbOverhang");
    expect(reason).toHaveTextContent("150");
    expect(reason).toHaveTextContent("Read length minus one.");
    expect(reason).toHaveTextContent("read_length = 151");
    expect(await within(reason).findByText("measured")).toBeInTheDocument();
    fireEvent.click(within(reason).getByRole("button", { name: "Change it" }));
    expect(p.onChange).toHaveBeenCalledWith("star_align");
    fireEvent.click(within(reason).getByRole("button", { name: "Ask about it in the chat" }));
    expect(p.onAsk).toHaveBeenCalledWith("About STAR_ALIGN sjdbOverhang: ");
  });

  it("says to pick a line until one is picked", () => {
    file();
    expect(screen.getByRole("complementary", { name: "the reason" })).toHaveTextContent(
      "Click a value in the file to see why it is what it is.");
  });
});

describe("the Nextflow it compiles to", () => {
  it("compiles on request, and shows main.nf and nextflow.config", async () => {
    file();
    expect(screen.queryByRole("tab", { name: "main.nf" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Compile it" }));
    fireEvent.click(await screen.findByRole("tab", { name: "main.nf" }));
    expect(await screen.findByText(/STAR_ALIGN\(\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "nextflow.config" }));
    expect(await screen.findByText(/docker.enabled = true/)).toBeInTheDocument();
  });

  it("says why when there is nothing to compile yet", async () => {
    emitted = { ok: false, status: 422, body: { detail: "MI0219: there is no pipeline to compile yet: empty" } };
    file();
    fireEvent.click(screen.getByRole("button", { name: "Compile it" }));
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

  it("says why there is no file when the preview is outdated", () => {
    file({ preview: { revision: 4, state: "outdated", text: "", findings: [] } });
    expect(screen.getByTestId("preview-outdated")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download pipeline.yml" })).toBeDisabled();
  });
});

describe("the file's sections", () => {
  it("offers a chip for each section the file has, and takes the file to it", () => {
    file();
    const chips = within(screen.getByRole("navigation", { name: "sections of the file" })).getAllByRole("button");
    expect(chips.map((c) => c.textContent)).toEqual(["Steps 3", "Checks"]);
    const gate = line("gate: null");
    gate.scrollIntoView = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Checks" }));
    expect(gate.scrollIntoView).toHaveBeenCalled();
  });
});
