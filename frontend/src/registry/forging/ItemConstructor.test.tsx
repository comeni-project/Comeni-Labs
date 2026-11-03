import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import fixture from "./constructors.fixture.json";
import { ItemConstructor } from "./ItemConstructor";
import type { ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

const choices = { types: [{ id: "assembly.fasta", name: "Assembly", family: "assembly", family_says: "Assembled sequences",
  explain: "Assembled sequences", made_by: [], read_by: [] }], roles: [], tools: [] };
function mount(piece: string, item?: ItemView, submit = vi.fn().mockResolvedValue({})) {
  vi.stubGlobal("fetch", vi.fn(async (url) => ({ ok: true, json: async () => String(url).endsWith("/choices") ? choices : fixture })));
  const actions = { command: { mutateAsync: submit } } as unknown as ReturnType<typeof useForgeActions>;
  render(<QueryClientProvider client={makeClient()}><ItemConstructor id="a1" piece={piece}
    items={item ? [item] : []} item={item} actions={actions} /></QueryClientProvider>);
  return submit;
}
function existing(key: string, value: unknown): ItemView {
  return { key, piece: key.split(":")[0], current_n: 7, status: "approved", value, revisions: [] } as ItemView;
}
afterEach(() => vi.unstubAllGlobals());

it("constructs a question answer from a source channel and registry picker", async () => {
  const submit = mount("questions");
  fireEvent.change(await screen.findByLabelText("What are you adding?"), { target: { value: "questions:input_type" } });
  fireEvent.change(screen.getByLabelText("Module channel"), { target: { value: "fasta" } });
  expect(screen.getByDisplayValue("fasta").getAttribute("list")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Choose type from the registry" }));
  const picker = await screen.findByRole("dialog", { name: "Choose a type" });
  fireEvent.click(within(picker).getByRole("button", { name: "Use assembly.fasta" }));
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "answer", item: "questions:input_type:fasta",
    expected: undefined, value: { choice: "assembly.fasta" } }));
  expect(await screen.findByRole("status")).toHaveTextContent("Saved fasta.");
  expect(screen.getByLabelText("Module channel")).toHaveValue("");
});

it("retains a setting and inline refusal until the server accepts the corrected value", async () => {
  const submit = vi.fn().mockRejectedValueOnce(new Error("MF0509: setting is passed nowhere")).mockResolvedValue({});
  mount("parameters", existing("parameters:param:min_contig", { name: "min_contig", position: 0, default: 500,
    domain: { kind: "integer", minimum: 100 }, via: "ext", key: "args", template: "--min-contig {value}", because: "QUAST default" }), submit);
  fireEvent.change(await screen.findByLabelText("Default"), { target: { value: "750" } });
  expect(screen.getByLabelText("Setting preview")).toHaveTextContent("--min-contig 750");
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("MF0509");
  expect(screen.getByLabelText("Default")).toHaveValue(750);
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved min_contig.")).toBeTruthy();
  expect(submit.mock.calls[1][0]).toEqual({ move: "change", item: "parameters:param:min_contig", expected: 7,
    value: { name: "min_contig", position: 0, default: 750, domain: { kind: "integer", minimum: 100 },
      via: "ext", key: "args", template: "--min-contig {value}", because: "QUAST default" } });
});

it("can construct nothing-needed without knowing an item key", async () => {
  const submit = mount("rules");
  fireEvent.change(await screen.findByLabelText("What are you adding?"), { target: { value: "rules:none" } });
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "No competing tool" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "write", item: "rules:none", expected: undefined,
    value: { because: "No competing tool" } }));
});

it.each([
  ["contract:input:reads", { name: "reads", position: 0, accepts: [{ type_id: "alignment.bam", states: ["sorted"] }], cardinality: "*" }],
  ["contract:nf_inputs", [{ ports: ["reads", "reference"], join: "broadcast" }, { literal: false }]],
  ["vocabulary:type:qc.report", { id: "qc.report", add_states: ["assembly"] }],
  ["vocabulary:measurement:read_length", { id: "read_length", kind: "integer", describes: "fastq.reads", meta_values: [{ when: 1, then: true }] }],
  ["rules:rule:alignment", { decides: [{ effect: "param", of: "alignment", name: "threads", when_implementation: ["nf-core/bwa/mem@1"] }],
    rows: [{ when: { read_length: ">= 100", paired: true }, then: 4, because: "Evidence" }], cite: "Source" }],
  ["tests:test:small", { inputs: { reads: ["a/b.fq"] }, setup: [{ tool: "nf-core/x@1", inputs: { reference: ["a/ref.fa"] }, feeds: { bam: "reads" } }],
    params: { threads: 2, paired: true }, expect: [{ port: "bam", pattern: "*.bam" }], unchecked: { log: "Variable name" } }],
])("editing %s preserves every nested value", async (key, value) => {
  const submit = mount(key.split(":")[0], existing(key, value));
  fireEvent.click(await screen.findByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "change", item: key, expected: 7, value }));
  expect(document.querySelector("textarea")).toBeNull();
});

it("disables duplicate saves while a command is pending", async () => {
  let done!: () => void;
  const submit = vi.fn(() => new Promise<void>((resolve) => { done = resolve; }));
  mount("vocabulary", existing("vocabulary:role:qc", { name: "qc", explain: "Quality checking" }), submit);
  fireEvent.click(await screen.findByRole("button", { name: "Save" }));
  expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  done();
  expect(await screen.findByRole("status")).toHaveTextContent("Saved qc.");
});

it("edits an added state through the extension branch without losing its type id", async () => {
  const submit = mount("vocabulary", existing("vocabulary:type:qc.report", { id: "qc.report", add_states: ["assembly"] }));
  fireEvent.change(await screen.findByLabelText("States to add 1"), { target: { value: "reads" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "change", item: "vocabulary:type:qc.report", expected: 7,
    value: { id: "qc.report", add_states: ["reads"] } }));
});

it("switching a type declaration to a state extension retains the constructed identity", async () => {
  const submit = mount("vocabulary");
  fireEvent.change(await screen.findByLabelText("Item name"), { target: { value: "qc.report" } });
  fireEvent.change(screen.getByLabelText("Data type or added states kind"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "Add states to add" }));
  fireEvent.change(screen.getByLabelText("States to add 1"), { target: { value: "assembly" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "write", item: "vocabulary:type:qc.report", expected: undefined,
    value: { id: "qc.report", add_states: ["assembly"] } }));
});

it("changing a setting route clears argument fields that no longer apply", async () => {
  const submit = mount("parameters", existing("parameters:param:threads", { name: "threads", position: 0,
    via: "ext", key: "args", template: "--threads {value}", default: 4, domain: { kind: "integer" } }));
  fireEvent.change(await screen.findByLabelText("Pass through"), { target: { value: "meta" } });
  expect(screen.getByLabelText("Setting preview")).toHaveTextContent("meta.threads = 4");
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "change", item: "parameters:param:threads", expected: 7,
    value: { name: "threads", position: 0, via: "meta", default: 4, domain: { kind: "integer" } } }));
});

it("a background refresh cannot advance the revision of the value being edited", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => fixture })));
  const submit = vi.fn().mockResolvedValue({});
  const actions = { command: { mutateAsync: submit } } as unknown as ReturnType<typeof useForgeActions>;
  const client = makeClient();
  const old = existing("vocabulary:role:qc", { name: "qc", explain: "Original explanation" });
  const draw = (item: ItemView) => <QueryClientProvider client={client}><ItemConstructor id="a1" piece="vocabulary"
    items={[item]} item={item} actions={actions} /></QueryClientProvider>;
  const view = render(draw(old));
  await screen.findByLabelText("Explain");
  fireEvent.change(screen.getByLabelText("Explain"), { target: { value: "My explanation" } });
  view.rerender(draw({ ...old, current_n: 8, value: { name: "qc", explain: "Changed by another tab" } }));
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(submit).toHaveBeenCalledWith({ move: "change", item: old.key, expected: 7,
    value: { name: "qc", explain: "My explanation" } }));
});
