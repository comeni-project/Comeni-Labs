import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Picker } from "./Picker";

/** Click a port, get only what fits — and a reason for the order.
 *
 * The picker's value is the ORDER, not the filter. `n-bport`: *SAMTOOLS_SORT is first because it
 * is the only producer of the state FEATURECOUNTS asks for* — a fact the registry produced.
 */

const ANSWER = {
  candidates: [
    { contract_id: "nf-core/samtools/sort@1.21.0", port: "bam", process: "SAMTOOLS_SORT",
      tool: "samtools/sort", surplus: 0, priority: 0,
      why: "the only producer of alignment.bam[coordinate_sorted]" },
  ],
  total: 12,
};

const PORT = {
  name: "bam", type_id: "alignment.bam", side: "in", met: false,
  states: ["coordinate_sorted"],
};

function at(answer: unknown = ANSWER, port = PORT, onPick = vi.fn()) {
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: true, status: 200, json: async () => answer,
  })));
  render(
    <QueryClientProvider client={makeClient()}>
      <Picker port={port as never} node="counts" at={{ x: 0, y: 0 }}
              onPick={onPick} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  return onPick;
}

afterEach(() => vi.unstubAllGlobals());

describe("the port picker", () => {
  it("asks the question the port actually asks, states included", async () => {
    // **The states are the difference between a filtered list and an answer.** Without them the
    // question is *what produces a BAM* — three contracts — when featureCounts asks for
    // `alignment.bam[coordinate_sorted]`, whose answer is one. `PortView.states` was added for
    // exactly this.
    at();
    await screen.findByTestId("candidate");
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain("type_id=alignment.bam");
    expect(url).toContain("states=coordinate_sorted");
    expect(url).toContain("side=producing");
  });

  it("asks the other question from an output", async () => {
    // An output asks what would ACCEPT it. Only the producing direction carries the resolver's
    // ordering, and `services/candidates.py` says so rather than claiming it for both.
    at(ANSWER, { ...PORT, side: "out" });
    await screen.findByTestId("candidate");
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("side=consuming");
  });

  it("shows the reason the server computed, never one of its own", async () => {
    at();
    const row = await screen.findByTestId("candidate");
    expect(row.textContent).toContain("the only producer of alignment.bam[coordinate_sorted]");
  });

  it("counts what fits against what exists", async () => {
    at();
    await screen.findByTestId("candidate");
    expect(screen.getByText("1 of 12")).toBeTruthy();
  });

  it("says nothing fits rather than showing an empty box", async () => {
    // Absence is absence, and here it is informative: nothing in this registry can feed this
    // port is a fact about the registry, not an empty search result.
    at({ candidates: [], total: 12 });
    await waitFor(() =>
      expect(screen.getByText(/nothing in this registry can connect here/)).toBeTruthy());
  });

  it("can be driven from the keyboard", async () => {
    // The 2026-08-29 walk found the module palette absent from the accessibility tree. A
    // popover that opens under the cursor and can only be used with it would be that defect
    // rebuilt one screen along.
    const onPick = at();
    await screen.findByTestId("candidate");
    fireEvent.keyDown(screen.getByTestId("picker"), { key: "Enter" });
    expect(onPick).toHaveBeenCalledWith("nf-core/samtools/sort@1.21.0", "bam");
  });
});
