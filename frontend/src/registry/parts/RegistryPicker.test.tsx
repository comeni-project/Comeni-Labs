import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { RegistryPicker, type PickerEntry } from "./RegistryPicker";

const entries: PickerEntry[] = [
  { id: "alignment.bam", name: "aligned reads (BAM)", group: "alignment", says: "Reads placed on a reference",
    before: ["nf-core/star/align@2.7.11b"], after: ["nf-core/samtools/sort@1.24"] },
  { id: "annotation.gtf", name: "gene annotation (GTF)", group: "annotation", says: "Where each gene lies",
    before: [], after: ["nf-core/star/align@2.7.11b"] },
  { id: "qc.report", name: "quality-control report", group: "qc", says: "A report", before: [], after: [] },
];

function show(extra: Partial<Parameters<typeof RegistryPicker>[0]> = {}) {
  const onPick = vi.fn();
  const onClose = vi.fn();
  render(<RegistryPicker title="Choose a type" entries={entries} before="Made by" after="Read by"
                         onPick={onPick} onClose={onClose} {...extra} />);
  return { onPick, onClose };
}

it("opens listing everything, with the closest pinned first", () => {
  show({ closest: ["annotation.gtf"] });
  const names = screen.getAllByRole("option").map((o) => o.textContent);
  expect(names).toHaveLength(3);
  expect(names[0]).toContain("gene annotation (GTF)");
  expect(screen.getByText("Closest")).toBeTruthy();
});

it("narrows as you type, by id, name or meaning", () => {
  show();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "gene lies" } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } });
  expect(screen.queryAllByRole("option")).toHaveLength(0);
  expect(screen.getByText(/Nothing in the registry matches/)).toBeTruthy();
});

it("narrows by group, and counts what each group holds", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /^qc/ }));
  expect(screen.getAllByRole("option")).toHaveLength(1);
});

it("shows what makes and reads the option in view, in full", () => {
  show();
  fireEvent.mouseEnter(screen.getAllByRole("option")[0]);
  const detail = screen.getByRole("region", { name: "alignment.bam" });
  expect(within(detail).getByText("nf-core/star/align@2.7.11b")).toBeTruthy();
  expect(within(detail).getByText("nf-core/samtools/sort@1.24")).toBeTruthy();
});

it("says plainly when nothing makes a type", () => {
  show({ closest: ["annotation.gtf"], emptyBefore: "Nothing: a person supplies it" });
  expect(screen.getByText("Nothing: a person supplies it")).toBeTruthy();
});

it("hands back the id chosen", () => {
  const { onPick } = show();
  fireEvent.click(screen.getAllByRole("option")[1]);
  fireEvent.click(screen.getByRole("button", { name: "Use annotation.gtf" }));
  expect(onPick).toHaveBeenCalledWith("annotation.gtf");
});

it("closes on Escape", () => {
  const { onClose } = show();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(onClose).toHaveBeenCalled();
});

it("offers a new name only where one is allowed", () => {
  const onNew = vi.fn();
  show({ onNew, newLabel: "New type" });
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "annotation.gff" } });
  fireEvent.click(screen.getByRole("button", { name: /New type “annotation.gff”/ }));
  expect(onNew).toHaveBeenCalledWith("annotation.gff");
});

it("opens on the current answer, marked as chosen", () => {
  show({ chosen: "qc.report" });
  expect(screen.getByRole("region", { name: "qc.report" })).toBeTruthy();
  expect(screen.getByRole("option", { name: /quality-control report/ }).textContent).toContain("✓");
});
