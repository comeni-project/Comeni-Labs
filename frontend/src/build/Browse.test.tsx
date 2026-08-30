import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Browse } from "./Browse";

/** Find a tool, over the canvas, without a mouse. */

const MODULES = [
  // **Two roles on one tool**, which is the whole point of the first test. Real: `trimgalore`
  // both trims and reports per-sample QC, and the palette showed it under one of them.
  { contract_id: "nf-core/trimgalore@0.6.10", tool: "trimgalore", process: "TRIMGALORE",
    roles: ["trimming", "qc_per_sample"], needs: ["fastq.reads"], makes: ["fastq.reads"],
    container: "x" },
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "y" },
];

function at(props: Partial<Parameters<typeof Browse>[0]> = {}) {
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: true, status: 200, json: async () => MODULES,
  })));
  const onAdd = props.onAdd ?? vi.fn();
  render(
    <QueryClientProvider client={makeClient()}>
      <Browse onAdd={onAdd} onClose={props.onClose ?? vi.fn()} accepts={props.accepts} />
    </QueryClientProvider>,
  );
  return onAdd;
}

afterEach(() => vi.unstubAllGlobals());

describe("the browse overlay", () => {
  it("shows a tool under EVERY role it declares, not the first", async () => {
    // **The defect this replaces.** `Modules.tsx` grouped by `roles[0]`, so a tool that both
    // trims and QCs was invisible under one of its two jobs — and `ModuleView.roles` has always
    // been a list. `impl-walkbugs` names it.
    at();
    await screen.findAllByTestId("browse-card");

    expect(screen.getByText(/^trimming · 1$/)).toBeTruthy();
    expect(screen.getByText(/^qc per sample · 1$/)).toBeTruthy();

    const trimgalore = screen.getAllByTestId("browse-card")
      .filter((c) => c.textContent?.includes("TRIMGALORE"));
    expect(trimgalore.length).toBe(2);
  });

  it("shows the type signature and invents no prose", async () => {
    // #78 and `impl-reuse`: `ModuleContract` has no description field, so *the type signature is
    // the description that ships today* and the slot is left EMPTY. The artboard draws a
    // sentence per tool; a plausible invented one is worse than none on a screen whose whole
    // claim is that nothing was guessed.
    at();
    const cards = await screen.findAllByTestId("browse-card");
    const star = cards.find((c) => c.textContent?.includes("STAR_ALIGN"))!;

    expect(star.textContent).toContain("fastq.reads → alignment.bam");
    expect(star.textContent).toContain("nf-core/star/align@1.11.0");
    // Nothing sentence-shaped: no full stop outside the contract id's version.
    expect(star.textContent).not.toMatch(/[a-z]{4,}\s[a-z]{4,}\s[a-z]{4,}\./);
  });

  it("marks what cannot fit rather than hiding it", async () => {
    // Hiding it answers *why is SALMON_QUANT not in this list* with silence.
    at({ accepts: { label: "alignment.bam", ids: new Set(["nf-core/star/align@1.11.0"]) } });
    await screen.findAllByTestId("browse-card");

    // The filter is on by default when there is one, so turn it off to see everything.
    fireEvent.click(screen.getByTestId("filter-accepts"));
    await waitFor(() => expect(screen.getAllByTestId("browse-card").length).toBeGreaterThan(1));
    expect(screen.getAllByText(/won't fit here/).length).toBeGreaterThan(0);
  });

  it("counts what is shown against what exists", async () => {
    at();
    await screen.findAllByTestId("browse-card");
    expect(screen.getByText("2 of 2")).toBeTruthy();
  });

  it("searches by tool, process and role", async () => {
    at();
    await screen.findAllByTestId("browse-card");
    fireEvent.change(screen.getByLabelText("search tools"), { target: { value: "alignment" } });
    await waitFor(() =>
      expect(screen.getAllByTestId("browse-card").every(
        (c) => c.textContent?.includes("STAR_ALIGN"))).toBe(true));
  });

  it("is keyboard-first rather than keyboard-patched", async () => {
    const onAdd = at();
    await screen.findAllByTestId("browse-card");
    fireEvent.keyDown(screen.getByTestId("browse"), { key: "ArrowDown" });
    fireEvent.keyDown(screen.getByTestId("browse"), { key: "Enter" });
    expect(onAdd).toHaveBeenCalled();
  });
});
