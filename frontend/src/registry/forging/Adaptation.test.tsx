import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";

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
    const reply = Object.entries(extra).find(([path]) => String(url).endsWith(path))?.[1] ?? view;
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
  expect(within(chat).getByText(/about parameters:param:min_contig/)).toBeTruthy();
});

it("an AI proposal in the chat can be approved there", async () => {
  const proposal = { seq: 2, role: "ai", item: null, content: "Here's a revision.", pending: false,
    at: "2026-10-30T10:01:00Z",
    commands: [{ move: "revise", item: "parameters:param:min_contig", value: { default: 200 },
                 because: "viral", n: 1 }] };
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters",
                     items: [ANSWERED, PARAM], messages: [proposal] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  fireEvent.click(within(chat).getByRole("button", { name: "Approve" }));
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

it("writing an item that exists names its revision", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  await screen.findByRole("group", { name: "min_contig" });
  fireEvent.change(screen.getByLabelText("Item"), { target: { value: "parameters:param:min_contig" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect((sent?.body as { expected: number }).expected).toBe(1);
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
