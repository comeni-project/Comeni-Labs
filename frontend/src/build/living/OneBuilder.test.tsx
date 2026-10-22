import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DraftGraph } from "../../api/types";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";

/** **One builder** (#395): the manual builder's controls on the one canvas. Each sends the whole
 *  next graph through `onEdit`, which the server reads as intent and the chat confirms. */

const GRAPH: DraftGraph = {
  ...FAKE_SESSION.graph,
  nodes: [...FAKE_SESSION.graph.nodes,
    { id: "samtools_sort", contract_id: "nf-core/samtools/sort@1.21.0", params: [] }],
};

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

function canvas(extra: Partial<React.ComponentProps<typeof LivingCanvas>> = {}) {
  const onEdit = vi.fn();
  mount(
    <LivingCanvas graph={GRAPH} ghost={null} positions={{ ...FAKE_SESSION.placement,
                    samtools_sort: { x: 900, y: 40 } }}
                  steps={FAKE_STEPS} channels={FAKE_CHANNELS} authors={{}} selected={null}
                  onSelect={vi.fn()} onEdit={onEdit} {...extra} />,
  );
  return onEdit;
}

const port = (node: string, label: RegExp) =>
  within(screen.getByTestId(`ports-${node}`)).getByRole("button", { name: label });

afterEach(() => vi.unstubAllGlobals());

describe("the manual builder's controls, on the one canvas", () => {
  it("removes the selected step with Delete, wires and all", () => {
    const onEdit = canvas({ selected: "trimgalore" });
    fireEvent.keyDown(window, { key: "Delete" });
    const [next] = onEdit.mock.calls[0];
    expect(next.nodes.map((n: { id: string }) => n.id)).not.toContain("trimgalore");
    expect(next.edges.some((e: { from_node: string }) => e.from_node === "trimgalore")).toBe(false);
  });

  it("does nothing on Delete while a field has focus", () => {
    const onEdit = canvas({ selected: "trimgalore" });
    const field = document.createElement("input");
    document.body.appendChild(field);
    fireEvent.keyDown(field, { key: "Delete" });
    expect(onEdit).not.toHaveBeenCalled();
    field.remove();
  });

  it("draws a wire from an output to an input", () => {
    const onEdit = canvas();
    fireEvent.pointerDown(port("star_align", /^Output bam/), { clientX: 0, clientY: 0 });
    fireEvent.pointerUp(port("samtools_sort", /^Input bam/), { clientX: 300, clientY: 0 });
    const [next] = onEdit.mock.calls[0];
    expect(next.edges).toContainEqual(
      { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" });
  });

  it("detaches a wire", () => {
    const onEdit = canvas();
    fireEvent.click(screen.getByTestId("wire-hit-trimgalore-star_align"));
    const [next] = onEdit.mock.calls[0];
    expect(next.edges.some((e: { from_node: string; to_node: string }) =>
      e.from_node === "trimgalore" && e.to_node === "star_align")).toBe(false);
  });

  it("picks a step for an open port and wires it in", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => !url.includes("/candidates")
      ? { ok: false, status: 404, json: async () => ({ detail: "not here" }) }
      : ({ ok: true, status: 200, json: async () => ({
      candidates: [{ contract_id: "nf-core/subread/featurecounts@2.0.6", port: "bam",
                     process: "SUBREAD_FEATURECOUNTS", tool: "subread/featurecounts", surplus: 0,
                     priority: 0, why: "reads sorted alignments" }],
      total: 1 }) })));
    const onEdit = canvas();
    const out = port("samtools_sort", /^Output bam/);
    fireEvent.pointerDown(out, { clientX: 5, clientY: 5 });
    fireEvent.pointerUp(out, { clientX: 5, clientY: 5 });
    fireEvent.click(await screen.findByTestId("candidate"));
    const [next] = onEdit.mock.calls[0];
    const added = next.nodes.find((n: { contract_id: string }) =>
      n.contract_id === "nf-core/subread/featurecounts@2.0.6");
    expect(added).toBeDefined();
    expect(next.edges).toContainEqual(
      { from_node: "samtools_sort", from_port: "bam", to_node: added.id, to_port: "bam" });
  });

  it("zooms in, out and back", () => {
    canvas();
    const stage = screen.getByTestId("stage");
    const before = stage.style.transform;
    fireEvent.click(screen.getByRole("button", { name: "zoom in" }));
    expect(stage.style.transform).not.toBe(before);
    fireEvent.click(screen.getByRole("button", { name: "reset the view" }));
    expect(stage.style.transform).toBe(before);
    fireEvent.click(screen.getByRole("button", { name: "zoom out" }));
    expect(stage.style.transform).not.toBe(before);
  });

  it("has no editing controls where the canvas is a preview", () => {
    canvas({ onEdit: undefined });
    expect(screen.queryByTestId("ports-star_align")).toBeNull();
    expect(screen.queryByTestId("wire-hit-trimgalore-star_align")).toBeNull();
  });
});

describe("the pipeline's name", () => {
  it("is renamed in place", () => {
    const onRename = vi.fn();
    mount(<LivingHeader session={{ ...FAKE_SESSION, name: "rnaseq" }} view="canvas" onView={vi.fn()}
                         onRun={vi.fn()} running={false} onRename={onRename} />);
    const name = screen.getByRole("textbox", { name: "pipeline name" });
    fireEvent.change(name, { target: { value: "rnaseq-star" } });
    fireEvent.blur(name);
    expect(onRename).toHaveBeenCalledWith("rnaseq-star");
  });
});
