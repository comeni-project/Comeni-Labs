import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import type { AnsweredStep } from "../../build/useBuilder";
import { OptionalInputs } from "./OptionalInputs";

const port = (name: string, extra: Record<string, unknown> = {}) =>
  ({ name, type_id: `t.${name}`, side: "in", accepts: [], optional: true, adds: [], met: false, states: [],
     gathers: false, state: "off", ...extra });

function draw(ports: unknown[], rules: unknown[]) {
  const onSwitch = vi.fn();
  const step = { id: "quast", process: "QUAST", ports, rules, settings: [] } as unknown as AnsweredStep;
  render(<QueryClientProvider client={makeClient()}><OptionalInputs step={step} onSwitch={onSwitch} /></QueryClientProvider>);
  return onSwitch;
}

const requires = { kind: "requires", when: ["gff"], names: ["fasta"], says: "gff is used only with fasta (QUAST needs a reference)",
                   applies: false, broken: false, at_run: false };

describe("optional inputs, by their rules (issues 460 and 511)", () => {
  it("says what each adds and what it needs", () => {
    draw([port("fasta", { adds: ["misassemblies"] }), port("gff")], [requires]);
    expect(within(screen.getByTestId("optional-fasta")).getByText("Adds misassemblies.")).toBeTruthy();
    expect(within(screen.getByTestId("optional-gff")).getByText(/Needs fasta/)).toBeTruthy();
    expect(within(screen.getByTestId("optional-fasta")).getByText("Needed when gff is used.")).toBeTruthy();
  });

  it("switching one on switches on what it needs", () => {
    const onSwitch = draw([port("fasta"), port("gff")], [requires]);
    fireEvent.click(within(screen.getByTestId("optional-gff")).getByRole("radio", { name: "Always" }));
    expect(onSwitch.mock.calls).toEqual([["gff", "required"], ["fasta", "required"]]);
  });

  it("an input another in use forbids is blocked, and says why", () => {
    const forbids = { kind: "forbids", when: ["bam"], names: ["reads"], says: "bam cannot be used with reads (one or the other)",
                      applies: true, broken: false, at_run: false };
    draw([port("bam", { state: "required" }), port("reads")], [forbids]);
    const reads = screen.getByTestId("optional-reads");
    expect(within(reads).getByText("Off because bam is on. Switch bam off to use this.")).toBeTruthy();
    expect((within(reads).getByRole("radio", { name: "Always" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("a choice of exactly one is a radio group, and picking one switches the others off", () => {
    const one = { kind: "one_of", when: [], names: ["a", "b"], says: "exactly one of a, b (pick a source)",
                  applies: true, broken: true, at_run: false };
    const onSwitch = draw([port("a"), port("b")], [one]);
    const group = screen.getByTestId("group-one_of");
    expect(within(group).getByText("Pick exactly one")).toBeTruthy();
    expect(within(group).getByRole("alert")).toHaveTextContent("exactly one of a, b");
    fireEvent.click(within(group).getByRole("radio", { name: "Use b" }));
    expect(onSwitch.mock.calls).toEqual([["a", "off"], ["b", "required"]]);
  });
});
