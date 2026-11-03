import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";
import constructors from "./constructors.fixture.json";

const rev = (n: number, move: string, actor: string, value: unknown, because = "") =>
  ({ n, move, actor, value, because, by: actor === "person" ? "rafael" : null, invocation: null });

const item = (key: string, piece: string, status: string, revisions: unknown[]) => ({
  key, piece, status, current_n: revisions.length,
  value: (revisions[revisions.length - 1] as { value: unknown }).value, revisions,
});

const BASE = {
  id: "a1", source: "nf-core", path: "quast", version: "5.3.0", base: "v0.4.0", reforge: null,
  depends_on: [], started_by: "rafael", started_at: "2026-10-30T10:00:00Z", abandoned_at: null,
  messages: [], ready: false,
};

const ANSWERED = item("questions:role", "questions", "approved",
  [rev(1, "answer", "person", { choice: "assembly_qc" })]);

const PARAM = item("parameters:param:min_contig", "parameters", "proposed",
  [rev(1, "draft", "ai", { position: 0, name: "min_contig", default: 500, via: "ext", key: "args" },
       "QUAST's default")]);

function at(view: object, extra: Record<string, unknown> = {}) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? "GET",
                 body: init?.body ? JSON.parse(String(init.body)) : null });
    const reply = Object.entries(extra).find(([path]) => String(url).endsWith(path))?.[1]
      ?? (String(url).endsWith("/constructors") ? constructors : String(url).includes("/context?") ? { lines: [], source_available: false,
        choices: [], decides: "Chooses the output content.", optional: false }
        : /\/(events|reviews)$/.test(String(url)) ? [] : view);
    const status = (reply as { refused?: boolean }).refused ? 422 : 200;
    return Promise.resolve({ ok: status === 200, status, json: async () => reply });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/forging/a1"] })} />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("a piece not started offers drafting with the AI or writing it yourself", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED] });
  const draft = await screen.findByRole("button", { name: "Draft with the AI" });
  expect(screen.getByRole("button", { name: "Write it myself" })).toBeTruthy();
  fireEvent.click(draft);
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/forge/adaptations/a1/draft")
    && (c.body as { piece: string }).piece === "contract")).toBe(true));
});

it("approve sends the command with the revision it was made against", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  const row = await screen.findByRole("group", { name: "min_contig" });
  fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toEqual({ move: "approve", item: "parameters:param:min_contig", expected: 1 });
  });
});

it("reject opens the chat on the item", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  const row = await screen.findByRole("group", { name: "min_contig" });
  fireEvent.click(within(row).getByRole("button", { name: "Reject" }));
  const chat = screen.getByRole("complementary", { name: "Chat with the AI" });
  expect(within(chat).getByText("about min_contig")).toBeTruthy();
});

it("an AI proposal in the chat can be approved there", async () => {
  const proposal = { seq: 2, role: "ai", item: null, content: "Here's a revision.", pending: false,
    at: "2026-10-30T10:01:00Z",
    commands: [{ move: "revise", item: "parameters:param:min_contig", value: { default: 200 },
                 because: "viral", n: 1 }] };
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters",
                     items: [ANSWERED, PARAM], messages: [proposal] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  fireEvent.click(within(chat).getByRole("button", { name: "Accept" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toEqual({ move: "approve", item: "parameters:param:min_contig", expected: 1 });
  });
});

it("a chat card a newer revision replaced says so and decides nothing", async () => {
  const proposal = { seq: 2, role: "ai", item: null, content: "Here's a revision.", pending: false,
    at: "2026-10-30T10:01:00Z",
    commands: [{ move: "draft", item: "parameters:param:min_contig", value: {}, because: "x", n: 1 }] };
  const revised = item("parameters:param:min_contig", "parameters", "proposed", [
    rev(1, "draft", "ai", { default: 500 }), rev(2, "revise", "ai", { default: 200 })]);
  at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, revised],
       messages: [proposal] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText(/Superseded/)).toBeTruthy();
  expect(within(chat).queryByRole("button", { name: "Approve" })).toBeNull();
});

it("a question is answered with its options, and has no Approve", async () => {
  const question = item("questions:role", "questions", "proposed", [rev(1, "draft", "ai", {
    asks: "Which role?", suggested: "assembly_qc", allows_new: true, options: [
      { id: "assembly_qc", label: "assembly QC", because: "it scores assemblies" },
      { id: "alignment", label: "alignment", because: "it aligns" }] })]);
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [question] });
  const row = await screen.findByRole("group", { name: "role" });
  expect(within(row).queryByRole("button", { name: "Approve" })).toBeNull();
  expect(within(row).getByText(/suggested/i)).toBeTruthy();
  fireEvent.click(within(row).getByRole("button", { name: /assembly QC/ }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toEqual({ move: "answer", item: "questions:role", expected: 1,
                                 value: { choice: "assembly_qc" } });
  });
});

it("a question can be answered with a name of the person's own", async () => {
  const question = item("questions:role", "questions", "proposed", [rev(1, "draft", "ai", {
    asks: "Which role?", allows_new: true, options: [] })]);
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [question] });
  const row = await screen.findByRole("group", { name: "role" });
  fireEvent.change(within(row).getByLabelText(/another answer/i), { target: { value: "binning" } });
  fireEvent.click(within(row).getByRole("button", { name: "Answer" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toEqual({ move: "answer", item: "questions:role", expected: 1,
                                 value: { choice: "binning", new: true } });
  });
});

it("a proposed removal says so, and Approve the rest leaves it for the person", async () => {
  const removing = item("parameters:param:threads", "parameters", "proposed", [
    rev(1, "draft", "ai", { default: 1 }), rev(2, "propose_removal", "ai", null, "unused")]);
  const others = ["a", "b"].map((name) => item(`parameters:param:${name}`, "parameters", "proposed",
    [rev(1, "draft", "ai", { default: 1 })]));
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters",
                     items: [ANSWERED, removing, ...others] });
  const row = await screen.findByRole("group", { name: "threads" });
  expect(within(row).getByText("The AI proposes removing this")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Approve the rest" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.url.endsWith("/commands")).length).toBe(2));
  expect(calls.filter((c) => c.url.endsWith("/commands"))
    .map((c) => (c.body as { item: string }).item)).not.toContain("parameters:param:threads");
});

it("a refused command reads the adaptation again, so a stale page catches up", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] },
                   { "/commands": { refused: true, detail: "MF0506: it changed since you looked" } });
  const row = await screen.findByRole("group", { name: "min_contig" });
  const reads = () => calls.filter((c) => c.method === "GET" && c.url.endsWith("/a1")).length;
  const before = reads();
  fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(reads()).toBeGreaterThan(before));
});

it("changing an item uses fields and sends its revision", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  const row = await screen.findByRole("group", { name: "min_contig" });
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  fireEvent.change(await within(row).findByLabelText("Default"), { target: { value: "700" } });
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toMatchObject({ move: "change", item: "parameters:param:min_contig", expected: 1,
      value: { position: 0, name: "min_contig", default: 700, via: "ext", key: "args" } });
  });
});

it("shows drafting while the AI works", async () => {
  at({ ...BASE, phase: "drafting", next_piece: "parameters", items: [ANSWERED] });
  expect(await screen.findByText(/drafting/i)).toBeTruthy();
});

it("all approved: assembling shows the files and the result", async () => {
  const assembled = { loaded: true, conforms: true, problems: [], blames: null,
                      files: ["tools/nf-core/quast/contract.yml"] };
  at({ ...BASE, phase: "reviewing", next_piece: null, ready: true, items: [ANSWERED] },
     { "/assemble": assembled });
  fireEvent.click(await screen.findByRole("button", { name: "Assemble" }));
  expect(await screen.findByText("tools/nf-core/quast/contract.yml")).toBeTruthy();
  expect(screen.getByText(/Loads over the registry/)).toBeTruthy();
});

const TESTED_ITEM = item("tests:test:small", "tests", "approved",
  [rev(1, "write", "person", { inputs: { reads: ["a/b.fq"] }, expect: [{ port: "bam", pattern: "*.bam" }] })]);
const ASSEMBLED = { ...BASE, phase: "assembled", next_piece: null, ready: true,
                    items: [ANSWERED, TESTED_ITEM], tests: [], tests_unavailable: null };

it("tests is a real piece, drafted like the others", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "tests", items: [ANSWERED] });
  const pieces = await screen.findByRole("navigation", { name: "Pieces" });
  expect(within(pieces).getByRole("button", { name: /tests/i })).toBeTruthy();
  expect(within(pieces).queryByText(/MVP 4/)).toBeNull();
  expect(screen.getByRole("heading", { name: "tests" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Draft with the AI" })).toBeTruthy();
});

it("run its tests starts them", async () => {
  const calls = at(ASSEMBLED);
  fireEvent.click(await screen.findByRole("button", { name: "Run its tests" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/forge/adaptations/a1/tests")
    && c.method === "POST")).toBe(true));
});

it("a running test shows its state and offers no second run", async () => {
  at({ ...ASSEMBLED, phase: "testing",
       tests: [{ name: "small", state: "running", run_id: "r1", says: null }] });
  expect(await screen.findByText("running in Wiener")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Run its tests" })).toBeNull();
});

it("a failure says what was missing, links the run and can run again", async () => {
  at({ ...ASSEMBLED, tests: [{ name: "small", state: "failed", run_id: "r1",
                               says: "output bam: nothing published matches *.bam" }] });
  expect(await screen.findByText(/nothing published matches/)).toBeTruthy();
  expect(screen.getByRole("link", { name: /open the run/i }).getAttribute("href")).toBe("/runs/r1");
  expect(screen.getByRole("button", { name: "Run its tests" })).toBeTruthy();
});

it("green says what it proves, and no more", async () => {
  at({ ...ASSEMBLED, phase: "tested",
       tests: [{ name: "small", state: "passed", run_id: "r1", says: null }] });
  expect(await screen.findByText(/not that its results are correct/)).toBeTruthy();
});

it("without Wiener it says why and offers nothing", async () => {
  at({ ...ASSEMBLED, tests_unavailable: "MF0514: no Wiener is configured to run tests" });
  expect(await screen.findByText(/no Wiener is configured/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Run its tests" })).toBeNull();
});

it("a test reads as what it feeds and what it expects", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "tests", items: [ANSWERED, item("tests:test:small",
    "tests", "proposed", [rev(1, "draft", "ai", { inputs: { reads: ["a/b.fq"] },
                                                   expect: [{ port: "bam", pattern: "*.bam" }] })])] });
  const row = await screen.findByRole("group", { name: "small" });
  expect(within(row).getByText("reads → *.bam")).toBeTruthy();
});

const TESTED = { ...ASSEMBLED, phase: "tested", publish_unavailable: null, pull_request: null,
                 tests: [{ name: "small", state: "passed", run_id: "r1", says: null }] };
const PULL = { number: 7, url: "https://github.com/x/y/pull/7", state: "open", checks: "pending",
               says: "still running: ci", merging: false };

it("open pull request starts it", async () => {
  const calls = at(TESTED);
  fireEvent.click(await screen.findByRole("button", { name: "Open pull request" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/forge/adaptations/a1/publish")
    && c.method === "POST")).toBe(true));
});

it("pending CI disables approve and says why", async () => {
  at({ ...TESTED, phase: "in_review", pull_request: PULL });
  const approve = await screen.findByRole("button", { name: "Approve pull request" });
  expect((approve as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Waiting for registry CI: still running: ci/)).toBeTruthy();
  expect(screen.getByRole("link", { name: /Pull request #7/ }).getAttribute("href")).toBe(PULL.url);
});

it("red CI says what failed and cannot be approved", async () => {
  at({ ...TESTED, phase: "in_review",
       pull_request: { ...PULL, checks: "red", says: "failed: lint" } });
  expect(await screen.findByText(/Registry CI failed: failed: lint/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve pull request" }) as HTMLButtonElement).disabled)
    .toBe(true);
});

it("green CI approves", async () => {
  const calls = at({ ...TESTED, phase: "in_review",
                     pull_request: { ...PULL, checks: "green", says: null } });
  fireEvent.click(await screen.findByRole("button", { name: "Approve pull request" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/forge/adaptations/a1/approve")
    && c.method === "POST")).toBe(true));
});

it("merging shows it, and offers no second click", async () => {
  at({ ...TESTED, phase: "in_review",
       pull_request: { ...PULL, checks: "green", says: null, merging: true } });
  expect((await screen.findByRole("button", { name: "Merging…" }) as HTMLButtonElement).disabled)
    .toBe(true);
});

it("merged says what comes next", async () => {
  at({ ...TESTED, phase: "merged", pull_request: { ...PULL, state: "merged", checks: "green" } });
  expect(await screen.findByText(/reaches the builder with the next release/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve pull request" })).toBeNull();
});

it("without a token it says why", async () => {
  at({ ...TESTED, publish_unavailable: "MF0516: no GitHub token is set to publish with" });
  expect(await screen.findByText(/no GitHub token is set/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Open pull request" })).toBeNull();
});

it("all approved: a piece can still be opened, and Assembly is one step back", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: null, ready: true, items: [ANSWERED] });
  await screen.findByRole("button", { name: "Assemble" });
  const pieces = screen.getByRole("navigation", { name: "Pieces" });
  fireEvent.click(within(pieces).getByRole("button", { name: /questions/i }));
  expect(await screen.findByRole("group", { name: "role" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Assemble" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Back to Assembly" }));
  expect(await screen.findByRole("button", { name: "Assemble" })).toBeTruthy();
});

const ASKED = item("questions:input_type:gff", "questions", "proposed", [rev(1, "draft", "ai",
  { asks: "What kind of file is it?", suggested: "annotation.gtf", allows_new: true,
    options: [{ id: "annotation.gtf", label: "annotation.gtf", because: "GTF" }] })]);
const CHOICES = { roles: [], tools: [], types: [
  { id: "annotation.gtf", name: "gene annotation (GTF)", explain: "Where genes lie", family: "annotation",
    family_says: "Features", made_by: [], read_by: ["nf-core/star/align@2.7.11b"] },
  { id: "genome.fasta", name: "reference genome (FASTA)", explain: null, family: "genome",
    family_says: "A reference genome", made_by: [], read_by: [] },
] };

it("a type can be chosen from everything the registry has", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [ASKED] },
                   { "/registry/choices": CHOICES });
  fireEvent.click(await screen.findByRole("button", { name: "Something else in the registry" }));
  const picker = await screen.findByRole("dialog", { name: "Choose a type" });
  fireEvent.click(within(picker).getByRole("option", { name: /reference genome/ }));
  fireEvent.click(within(picker).getByRole("button", { name: "Use genome.fasta" }));
  await vi.waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
    move: "answer", item: "questions:input_type:gff", value: { choice: "genome.fasta" } });
});

it("picking a pin opens the question that decides it", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: null, ready: true, items: [ASKED] });
  const tool = await screen.findByRole("group", { name: /The tool so far/ });
  fireEvent.click(within(tool).getByRole("button", { name: /gff/ }));
  expect(await screen.findByRole("group", { name: "gff" })).toBeTruthy();
});

it("the tool says how much of it is decided", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [ANSWERED, ASKED] });
  const tool = await screen.findByRole("region", { name: "The tool so far" });
  expect(within(tool).getByRole("heading", { name: "The tool so far" })).toBeTruthy();
  expect(within(tool).getByText("1 of 2 answered. Pick any part.")).toBeTruthy();
});

it("the picker floats over the page and closes from outside it", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [ASKED] }, { "/registry/choices": CHOICES });
  fireEvent.click(await screen.findByRole("button", { name: "Something else in the registry" }));
  await screen.findByRole("dialog", { name: "Choose a type" });
  fireEvent.click(screen.getByRole("button", { name: "Close the picker" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

const ENGINE = { seq: 1, role: "engine", item: "draft:contract", content: "The contract draft wasn't usable, so nothing was saved.",
                 commands: [], details: ["MF0507: not a port"], resolved: false, pending: false, at: "2026-11-01T10:00:00Z" };

it("while the AI works the chat shows what it is doing, with tokens", async () => {
  at({ ...BASE, phase: "drafting", next_piece: "contract", items: [ANSWERED] }, { "/events": [
    { seq: 1, kind: "started", data: { what: "drafting", piece: "contract" }, at: "2026-11-01T10:00:00Z" },
    { seq: 2, kind: "asking", data: { attempt: 1, attempts: 2, model: "gemma3:12b" }, at: "2026-11-01T10:00:00Z" },
    { seq: 3, kind: "called", data: { attempt: 1, input_tokens: 4379, output_tokens: 20, seconds: 9 }, at: "2026-11-01T10:00:09Z" },
    { seq: 4, kind: "asking", data: { attempt: 2, attempts: 2, model: "gemma3:12b" }, at: "2026-11-01T10:00:09Z" },
  ] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText("Drafting the contract")).toBeTruthy();
  expect(await within(chat).findByText(/attempt 2 of 2/)).toBeTruthy();
  expect(await within(chat).findByText(/4,379 tokens sent/)).toBeTruthy();
});

it("a refused draft is a sentence, with its detail tucked away and a way forward", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED], messages: [ENGINE] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText(/wasn't usable/)).toBeTruthy();
  expect(within(chat).queryByText("MF0507: not a port")).toBeNull();
  fireEvent.click(within(chat).getByRole("button", { name: "Details" }));
  expect(within(chat).getByText("MF0507: not a port")).toBeTruthy();
  fireEvent.click(within(chat).getByRole("button", { name: "Try again" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/draft") && (c.body as { piece: string }).piece === "contract")).toBe(true));
});

it("a refused draft that was later redone steps back", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED], messages: [{ ...ENGINE, resolved: true }] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText(/refused, then redone/)).toBeTruthy();
  expect(within(chat).queryByRole("button", { name: "Try again" })).toBeNull();
});

it("a reply that sent nothing says so, however confident its words", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED], messages: [
    { seq: 1, role: "ai", item: null, content: "Okay, I'll add them.", commands: [], details: [], resolved: false,
      pending: false, at: "2026-11-01T10:00:00Z" }] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText("No changes made")).toBeTruthy();
  expect(within(chat).getByRole("button", { name: "Redraft" })).toBeTruthy();
});

it("Redraft is offered only on the latest reply", async () => {
  const said = { role: "ai", item: null, content: "Okay.", commands: [], details: [], resolved: false, pending: false };
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED], messages: [
    { ...said, seq: 1, at: "2026-11-01T10:00:00Z" },
    { ...said, seq: 2, role: "person", at: "2026-11-01T10:01:00Z" }] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  expect(await within(chat).findByText("No changes made")).toBeTruthy();
  expect(within(chat).queryByRole("button", { name: "Redraft" })).toBeNull();
});

it("the tool diagram sits beside the chat, in the left column", async () => {
  const pin = item("questions:input_type:consensus", "questions", "approved", [rev(1, "draft", "ai", { choice: "assembly.fasta" })]);
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED, pin] });
  const tool = await screen.findByRole("region", { name: "The tool so far" });
  const chat = screen.getByRole("complementary", { name: "Chat with the AI" });
  expect(tool.parentElement?.contains(chat)).toBe(false);
  expect(tool.closest(".forge-body")?.contains(chat)).toBe(true);
});

it("the chat can be resized from the keyboard, and keeps its limits", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED] });
  const handle = await screen.findByRole("button", { name: /Resize the chat/ });
  const chat = screen.getByRole("complementary", { name: "Chat with the AI" });
  const width = () => chat.style.getPropertyValue("--chat-width");
  fireEvent.keyDown(handle, { key: "ArrowLeft" });
  expect(width()).toBe("404px");
  for (let n = 0; n < 40; n += 1) fireEvent.keyDown(handle, { key: "ArrowLeft" });
  expect(width()).toBe("620px");
});

it("shows question evidence and current reviewer advice alongside the answers", async () => {
  const q = { asks: "What does the table hold?", allows_new: true, suggested: "qc.report::assembly",
    options: [{ id: "qc.report::assembly", label: "Assembly metrics", because: "It measures an assembly", new: true }] };
  const question = item("questions:output_type:tsv", "questions", "proposed", [rev(1, "draft", "ai", q)]);
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [question] }, {
    "/context?item=questions%3Aoutput_type%3Atsv": {
      lines: [{ number: 20, text: "emit: tsv" }], source_available: true, upstream: "The metrics table",
      decides: "Chooses what the table holds.", optional: true,
      choices: [{ id: "qc.report::assembly", name: "quality report", explain: "Assembly quality metrics",
        scope: "sample", tools: [], proposed: true }],
    },
    "/reviews": [{ item: question.key, revision: 1, comment: "Check the assembly state.",
      quote: "emit: tsv", file: "main.nf", model: "recorded/reviewer" }],
  });
  expect(await screen.findByText("Chooses what the table holds.")).toBeTruthy();
  expect(await screen.findByText("Check the assembly state.")).toBeTruthy();
  expect(screen.getByText(/Declaring this output is optional/)).toBeTruthy();
  expect(screen.getByText("Proposed vocabulary · needs review")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Assembly metrics/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/commands"))?.body).toEqual({
    move: "answer", item: question.key, expected: 1, value: { choice: "qc.report::assembly", new: true },
  }));
});

it("does not display reviewer advice about an older revision", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [PARAM] }, {
    "/reviews": [{ item: PARAM.key, revision: 0, comment: "Outdated advice", quote: null,
      file: null, model: "recorded/reviewer" }],
  });
  await screen.findByRole("group", { name: "min_contig" });
  expect(screen.queryByText("Outdated advice")).toBeNull();
});

it("retains the question after answering and marks the person's choice without the old suggestion", async () => {
  const q = { asks: "What does the report hold?", suggested: "qc.report", options: [
    { id: "qc.report", label: "General report", because: "general" },
    { id: "qc.report::assembly", label: "Assembly report", because: "assembly metrics" },
  ] };
  at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [
    item("questions:output_type:tsv", "questions", "approved", [
      rev(1, "draft", "ai", q), rev(2, "answer", "person", { choice: "qc.report::assembly" }),
    ]),
  ] });
  const row = await screen.findByRole("group", { name: "tsv" });
  expect(within(row).getByText(q.asks)).toBeTruthy();
  expect(within(row).getByText("Output · tsv")).toBeTruthy();
  expect(within(row).getByRole("button", { name: /Assembly report/ }).getAttribute("aria-pressed")).toBe("true");
  expect(within(row).getByText("chosen by you")).toBeTruthy();
  expect(within(row).queryByText("suggested")).toBeNull();
});

it("orders the job before the input and output decisions", async () => {
  const q = { asks: "Choose", options: [] };
  at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [
    item("questions:output_type:tsv", "questions", "proposed", [rev(1, "draft", "ai", q)]),
    item("questions:input_type:fasta", "questions", "proposed", [rev(1, "draft", "ai", q)]),
    item("questions:role", "questions", "proposed", [rev(1, "draft", "ai", q)]),
  ] });
  await screen.findByRole("group", { name: "role" });
  const rows = screen.getAllByRole("group").filter((r) => r.hasAttribute("data-item"));
  expect(rows.map((r) => r.getAttribute("data-item"))).toEqual([
    "questions:role", "questions:input_type:fasta", "questions:output_type:tsv",
  ]);
});

it("an empty refused piece keeps the attempt visible on the page and tracker", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED] }, {
    "/events": [
      { seq: 1, kind: "started", data: { piece: "contract", what: "drafting" }, at: "2026-11-03T10:00:00Z" },
      { seq: 2, kind: "refused", data: { attempt: 1, problems: ["No process"] }, at: "2026-11-03T10:00:01Z" },
    ],
  });
  expect(await screen.findByText(/Read the attempt in the chat/)).toBeTruthy();
  expect(screen.getByText("draft refused · try again")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Draft with the AI" })).toBeTruthy();
});

it("a rejected question stays unresolved and has explicit removal with a recorded reason", async () => {
  const q = { asks: "What file type is meta?", options: [] };
  const rejected = item("questions:input_type:meta", "questions", "rejected", [
    rev(1, "draft", "ai", q), rev(2, "reject", "person", null),
  ]);
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [ANSWERED, rejected] });
  const row = await screen.findByRole("group", { name: "meta" });
  expect(within(row).getByText(/still needs an answer, correction or explicit removal/)).toBeTruthy();
  fireEvent.click(within(row).getByRole("button", { name: "Remove question" }));
  const form = within(row).getByRole("form", { name: "Remove meta question" });
  expect(within(row).queryByRole("button", { name: /^Answer$/ })).toBeNull();
  expect(within(form).getByRole("button", { name: "Remove question" })).toBeDisabled();
  fireEvent.change(within(form).getByLabelText("Why does this question not apply?"), {
    target: { value: "meta carries metadata, not a file" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "Remove question" }));
  await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/commands"))?.body).toEqual({
    move: "remove", item: "questions:input_type:meta", expected: 2,
    because: "meta carries metadata, not a file",
  }));
});

it("a refused removal keeps the reason and the revision being decided on", async () => {
  const q = item("questions:input_type:meta", "questions", "proposed", [
    rev(1, "draft", "ai", { asks: "What file is meta?", options: [] }),
  ]);
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "questions", items: [q] }, {
    "/commands": { refused: true, detail: "MF0506: it changed since you looked" },
  });
  const row = await screen.findByRole("group", { name: "meta" });
  fireEvent.click(within(row).getByRole("button", { name: "Remove question" }));
  const form = within(row).getByRole("form", { name: "Remove meta question" });
  fireEvent.change(within(form).getByLabelText("Why does this question not apply?"), {
    target: { value: "Metadata, not a file" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "Remove question" }));
  expect(await within(form).findByRole("alert")).toHaveTextContent("changed since you looked");
  expect(within(form).getByLabelText("Why does this question not apply?")).toHaveValue("Metadata, not a file");
  expect(calls.find((c) => c.url.endsWith("/commands"))?.body).toEqual({
    move: "remove", item: q.key, expected: 1, because: "Metadata, not a file",
  });
});

it("a process-only contract stays current instead of appearing approved in the tracker", async () => {
  const process = item("contract:process", "contract", "approved", [rev(1, "write", "person", {
    nf_process: "QUAST", nf_include: "tools/nf-core/quast/module/main.nf", roles: ["assembly_qc"],
  })]);
  at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED, process] });
  const tracker = await screen.findByRole("navigation", { name: "Pieces" });
  const contract = within(tracker).getByRole("button", { name: /contract/i });
  expect(contract.getAttribute("aria-current")).toBe("step");
  expect(contract.closest("li")?.getAttribute("data-state")).toBe("now");
});
