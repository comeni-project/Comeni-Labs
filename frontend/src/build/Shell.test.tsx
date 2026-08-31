import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** The builder's shell, and the report-back defects the 2026-08-29 walk found.
 *
 * That walk's conclusion was that **the modelling is sound and the surface is not** — the graph
 * model, the wire, validation, emission, the gate and the courier all did exactly what they
 * claim. Every defect below is a *feedback* defect.
 */

const MODULES = [
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "x" },
  { contract_id: "nf-core/hisat2/align@1.0.0", tool: "hisat2/align", process: "HISAT2_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "y" },
];

const PIPELINE = {
  steps: [{
    id: "star_align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@1.11.0",
    tier: 3, reason: "a rule matched",
    ports: [{ name: "bam", type_id: "alignment.bam", side: "out", met: true }],
    settings: [],
  }],
  channels: [],
  layout: {
    nodes: [{ id: "star_align", rank: 0, order: 0, x: 0, y: 0, width: 232, height: 78, tier: 3 }],
    wires: [], width: 232, height: 78,
  },
  provenance: { "3": 1 },
  settled_share: 1,
  needs_review: [],
};

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

function at(path = "/build", draft?: unknown) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const body = u.includes("/tiers") ? TIERS
      : u.includes("/modules") ? MODULES
      : u.includes("/pipeline/drafts/") && (init?.method ?? "GET") === "GET"
        ? (draft ?? { id: "d1", name: "atac-peaks", graph: { nodes: [], edges: [] } })
      : u.includes("/pipeline/drafts") ? { id: "d1", name: "", graph: { nodes: [], edges: [] } }
      : PIPELINE;
    return { ok: true, status: 200, json: async () => body };
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the builder's shell", () => {
  it("names the pipeline you opened, never another one", async () => {
    // **It was the literal string `RNA-seq spine`.** The walk deleted every step, replaced them
    // with two others, and the header still said the example's name — because it was never
    // reading anything. `PipelineDraft.name` had existed since 3E with nothing setting it.
    at("/build?draft=d1");
    const field = await screen.findByLabelText("pipeline name");
    await waitFor(() => expect((field as HTMLInputElement).value).toBe("atac-peaks"));
    expect(screen.queryByText("RNA-seq spine")).toBeNull();
  });

  it("opens the draft in the URL rather than the example", async () => {
    // Phase 2's front door links to `/build?draft=<id>` from every row of the *by pipeline*
    // table. Before this phase every one of those links opened the canonical spine.
    at("/build?draft=d1");
    await screen.findByLabelText("pipeline name");
    const asked = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(asked.some((u) => u.includes("/pipeline/drafts/d1"))).toBe(true);
  });

  it("offers exactly one control per action", async () => {
    // **The general form of a defect this screen had twice.** The walk found two stacked
    // *Send to Wiener* buttons — the rail rendered the step's label as a button and the panel
    // rendered the real control beneath it, both enabled, the visible one inert. The Gate step
    // had already been fixed for the same reason and the Run step was missed.
    //
    // Asserting the general rule rather than the instance is what stops the third one.
    at();
    await screen.findByTestId("builder");
    const names = Array.from(document.querySelectorAll("button, a[href]"))
      .filter((el) => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true")
      .map((el) => (el.textContent ?? "").trim().toLowerCase())
      .filter((name) => name.length > 0);
    const seen = new Set<string>();
    const twice = names.filter((name) => (seen.has(name) ? true : (seen.add(name), false)));
    expect(twice).toEqual([]);
  });

  it("says the verdict is being rechecked rather than describing a graph that is gone", async () => {
    // Mid-edit the panel read `UNMET MD0506 star_align.index` while `star_align` had already
    // been deleted, for 2–3s, with nothing marking it. The marker existed — `useBuilder` has
    // returned `settling` since 3E, documented as *only for a quiet indicator* — and no surface
    // ever rendered it.
    at();
    await screen.findByTestId("builder");
    // A fresh mount is mid-settle by construction: the debounce has not fired yet.
    expect(screen.getByTestId("status").textContent).toMatch(/checking/i);
  });

  it("can add a step without a pointer", async () => {
    // The palette was a bare `div draggable="true"` — no role, no tabindex, absent from the
    // accessibility tree, so drag and double-click were the only two ways in. Phase 3a gave it
    // a role and a key handler; 3b replaced it with an overlay that is keyboard-FIRST rather
    // than keyboard-patched: it focuses its search on open, and arrows and Enter walk it.
    at();
    await screen.findByTestId("builder");
    fireEvent.contextMenu(screen.getByTestId("canvas"));

    const overlay = await screen.findByTestId("browse");
    await screen.findAllByTestId("browse-card");
    fireEvent.keyDown(overlay, { key: "Enter" });

    await waitFor(() =>
      expect(vi.mocked(fetch).mock.calls.some((c) => String(c[0]).includes("/pipeline/draw")))
        .toBe(true));
  });
});
