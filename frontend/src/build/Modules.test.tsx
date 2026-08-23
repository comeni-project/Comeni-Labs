import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { MODULE_DND, Modules } from "./Modules";

const MODULES = [
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "x" },
];

function at(onAdd?: (id: string) => void) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => MODULES,
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Modules inPipeline={new Set()} onAdd={onAdd} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("adding a module from the palette", () => {
  it("carries the contract id under a type of its own", async () => {
    // Not `text/plain`: the canvas must not accept a paragraph dragged out of another window
    // and try to add it as a tool.
    at(() => {});
    const row = await screen.findByTestId("module-row");
    const setData = vi.fn();
    fireEvent.dragStart(row, { dataTransfer: { setData, effectAllowed: "" } });
    expect(setData).toHaveBeenCalledWith(MODULE_DND, "nf-core/star/align@1.11.0");
  });

  it("double-click adds too, because drag is the gesture people miss", async () => {
    const add = vi.fn();
    at(add);
    fireEvent.doubleClick(await screen.findByTestId("module-row"));
    expect(add).toHaveBeenCalledWith("nf-core/star/align@1.11.0");
  });

  it("is draggable only where something can receive it", async () => {
    // Plan 3C's rule, and the one this screen keeps earning: a control that moves under your
    // hand and does nothing is worse than one plainly not offered.
    at();
    const row = await screen.findByTestId("module-row");
    expect(row).not.toHaveAttribute("draggable", "true");
  });

  it("stops calling itself a placeholder once it is not one", async () => {
    at(() => {});
    await waitFor(() =>
      expect(screen.getByText(/double-click, to add a step/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Reference only — placeholder/)).toBeNull();
  });
});
