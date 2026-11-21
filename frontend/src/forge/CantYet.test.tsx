import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { CantYet } from "./ForgeHome";

function serve(wants: object[]) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => ({ wants }) })));
}

function shown(pick = vi.fn(), query = "") {
  render(<QueryClientProvider client={makeClient()}><CantYet query={query} pick={pick} /></QueryClientProvider>);
  return pick;
}

afterEach(() => vi.unstubAllGlobals());

it("names what builds asked for that the registry cannot make, with how many asked", async () => {
  serve([{ type_id: "assembly.fasta", name: "assembly sequences (FASTA)", builds: 2 },
         { type_id: "variants.vcf", name: "variant calls (VCF)", builds: 1 }]);
  shown();
  expect(await screen.findByText("Your registry can’t yet")).toBeTruthy();
  expect(screen.getByRole("button", { name: /Make assembly sequences \(FASTA\)\s*asked in 2 builds/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: /Make variant calls \(VCF\)\s*asked in 1 build$/ })).toBeTruthy();
});

it("searches the catalogue for a chip, and a second press clears it", async () => {
  serve([{ type_id: "assembly.fasta", name: "assembly sequences (FASTA)", builds: 2 }]);
  const pick = shown();
  fireEvent.click(await screen.findByRole("button", { name: /Make assembly sequences/ }));
  expect(pick).toHaveBeenCalledWith("assembly sequences (FASTA)");
});

it("shows nothing when every want can be made", async () => {
  serve([]);
  const { container } = render(
    <QueryClientProvider client={makeClient()}><CantYet query="" pick={vi.fn()} /></QueryClientProvider>);
  await new Promise((r) => setTimeout(r, 20));
  expect(container.textContent).toBe("");
});
