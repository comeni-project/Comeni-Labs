import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Swap } from "./Swap";

/** Swap shows, then asks. `n-bswap`: *a resolver that silently rewrites four things is
 *  indistinguishable from one that guessed.* */

const STEP = {
  id: "align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@1.11.0",
  tier: 3, reason: "a rule matched",
  ports: [
    { name: "reads", type_id: "fastq.reads", side: "in", met: true, states: [] },
    { name: "bam", type_id: "alignment.bam", side: "out", met: true, states: [] },
  ],
  settings: [],
};

const GRAPH = {
  nodes: [{ id: "align", contract_id: "nf-core/star/align@1.11.0", params: [] }],
  edges: [],
};

const OPTIONS = {
  candidates: [
    { contract_id: "nf-core/star/align@1.11.0", port: "bam", process: "STAR_ALIGN",
      tool: "star/align", surplus: 0, priority: 10, why: "produces alignment.bam" },
    { contract_id: "nf-core/hisat2/align@1.0.0", port: "bam", process: "HISAT2_ALIGN",
      tool: "hisat2/align", surplus: 0, priority: 0, why: "produces alignment.bam" },
  ],
  total: 12,
};

/** `now` validates clean; `would` reports a new unmet input. */
function at(would: unknown = { findings: [{ code: "MD0506", node: "align", port: "index" }] }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.includes("/candidates")) return { ok: true, status: 200, json: async () => OPTIONS };
    // **Which graph was sent, not which call this is.** Counting calls assumed an order
    // react-query does not promise — the two validations are independent queries and either
    // may resolve first. Reading the body is the question actually being asked.
    const sent = String(init?.body ?? "");
    const body = sent.includes("hisat2") ? would : { findings: [] };
    return { ok: true, status: 200, json: async () => body };
  }));
  const onApply = vi.fn();
  render(
    <QueryClientProvider client={makeClient()}>
      <Swap step={STEP as never} graph={GRAPH as never} onApply={onApply} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  return onApply;
}

afterEach(() => vi.unstubAllGlobals());

describe("swapping a step", () => {
  it("never offers the step you are already using", async () => {
    at();
    const options = await screen.findAllByTestId("swap-option");
    expect(options.length).toBe(1);
    expect(options[0].textContent).toContain("hisat2/align");
  });

  it("shows the consequences before anything is applied", async () => {
    // **Computed, not described.** The line is a finding `validate` produced about the graph as
    // it WOULD be — not a sentence predicting what it might say.
    const onApply = at();
    fireEvent.click(await screen.findByTestId("swap-option"));

    // **Wait for the CONTENT, not the container.** The panel appears immediately showing
    // "Reading what would change…", so asserting on its presence asserts on a spinner.
    // The text is split across elements — the code sits in its own `<span>` — so match the
    // line rather than a fragment of it.
    await waitFor(() =>
      expect(screen.getByTestId("consequences").textContent).toContain("would break"));
    expect(screen.getByTestId("consequences").textContent).toContain("MD0506 align.index");
    expect(onApply).not.toHaveBeenCalled();
  });

  it("applies nothing until it is asked to", async () => {
    const onApply = at();
    fireEvent.click(await screen.findByTestId("swap-option"));
    // The apply control is disabled while the preview is in flight — offering to apply a change
    // whose consequences have not arrived is the opposite of "shows, then asks".
    await waitFor(() =>
      expect(screen.getByTestId("apply-swap")).not.toBeDisabled());
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("apply-swap"));
    expect(onApply).toHaveBeenCalledWith("nf-core/hisat2/align@1.0.0");
  });

  it("says so when nothing would change, rather than showing an empty panel", async () => {
    at({ findings: [] });
    fireEvent.click(await screen.findByTestId("swap-option"));
    await waitFor(() =>
      expect(screen.getByText(/validates the same either way/)).toBeTruthy());
  });
});
