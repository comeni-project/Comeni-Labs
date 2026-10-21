import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunSheet } from "./RunSheet";
import type { AnsweredStep } from "./useBuilder";

/** The run sheet (#379): numbered sections on the left, and a summary holding the one action. */

const setting = (name: string, tier: number, value: string | null) =>
  ({ name, value, via: "ext", tier, reason: `why ${name}`, because: "", axis_reason: "", premise: [] });

const STEPS = [
  { id: "star_align", process: "STAR_ALIGN", contract_id: "c/a", runs: "per_item", tier: 3, reason: "", ports: [],
    settings: [setting("sjdbOverhang", 3, "150")] },
  { id: "featurecounts", process: "SUBREAD_FEATURECOUNTS", contract_id: "c/f", runs: "per_item", tier: 4,
    reason: "", ports: [], settings: [setting("strandedness", 4, null)] },
] as unknown as AnsweredStep[];

const SOURCES = [
  { key: "reads", name: "reads", type_id: "fastq.reads" },
  { key: "fasta", name: "fasta", type_id: "genome.fasta" },
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404, json: async () => ({ detail: "not here" }) })));
});
afterEach(() => vi.unstubAllGlobals());

function sheet(overrides: Partial<Parameters<typeof RunSheet>[0]> = {}) {
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <RunSheet name="rnaseq-counts" steps={STEPS} sources={SOURCES} draftId="d1" gated onClose={onClose}
                  {...overrides} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onClose;
}

describe("the run sheet", () => {
  it("is titled for the pipeline it runs", () => {
    sheet();
    expect(screen.getByRole("dialog", { name: "Run rnaseq-counts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Run rnaseq-counts" })).toBeInTheDocument();
  });

  it("goes through Your files, then the values still open, in that order, as the board numbers them", () => {
    sheet();
    const sections = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(sections.filter((s) => ["Checked", "Your files", "Values still open"].includes(s ?? "")))
      .toEqual(["Your files", "Values still open"]);
  });

  it("lists each file the pipeline needs with its type", () => {
    sheet();
    const files = screen.getByRole("region", { name: "Your files" });
    expect(within(files).getByText("reads")).toBeInTheDocument();
    expect(within(files).getByText("genome.fasta")).toBeInTheDocument();
  });

  it("lists the open values with their step and reason, and says the run may go ahead", () => {
    sheet();
    const open = screen.getByRole("region", { name: "Values still open" });
    expect(open).toHaveTextContent("strandedness");
    expect(open).toHaveTextContent("SUBREAD_FEATURECOUNTS");
    expect(open).toHaveTextContent("why strandedness");
    expect(open).toHaveTextContent("You can run with these open");
  });

  it("draws no open section when every value is decided", () => {
    sheet({ steps: STEPS.slice(0, 1) });
    expect(screen.queryByRole("region", { name: "Values still open" })).toBeNull();
  });

  it("sums up the run beside the one action", () => {
    sheet();
    const summary = screen.getByRole("complementary", { name: "Ready to run" });
    expect(within(summary).getByRole("row", { name: /Steps/ })).toHaveTextContent("2");
    expect(within(summary).getByRole("row", { name: /Inputs/ })).toHaveTextContent("2");
    expect(within(summary).getByRole("row", { name: /Values open/ })).toHaveTextContent("1");
    expect(within(summary).getByRole("row", { name: /Where/ })).toHaveTextContent("this machine");
    expect(within(summary).getByTestId("send-to-wiener")).toBeInTheDocument();
  });

  it("says what waits before the pipeline is kept", () => {
    sheet({ draftId: null, gated: false });
    expect(within(screen.getByRole("complementary", { name: "Ready to run" }))
      .getByText("Keep this pipeline first.")).toBeInTheDocument();
  });

  it("says whether the check passed as the summary's line, under the action", () => {
    sheet();
    const summary = screen.getByRole("complementary", { name: "Ready to run" });
    expect(within(summary).getByTestId("sheet-checked")).toHaveTextContent(/^Checked/);
  });

  it("is drawn in the page, not over it, when the builder asks for it there", () => {
    sheet({ inline: true });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("region", { name: "Run rnaseq-counts" })).toBeInTheDocument();
  });

  it("closes on Escape and on Cancel", () => {
    const onClose = sheet();
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
