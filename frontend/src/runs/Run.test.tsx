import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const STATE = {
  run_id: "4c1e9a07b2f1de40", phase: "running",
  counts: { succeeded: 2, failed: 0, cached: 0, running: 1, submitted: 0 },
  started_at_ms: 1787517649000, ended_at_ms: null,
};

const OVERVIEW = {
  rows: [{
    process: "TRIMGALORE", declared: true, reached: true,
    tasks: 1, done: 1, running: 0, failed: 0, cached: 0, attempts_max: 1,
    memory_asked_bytes: 1073741824, memory_peak_bytes: 8785920,
    cpus_asked: 6, cpu_used_pct: 202.4,
    realtime_ms: 343, queue_wait_ms: 617, read_bytes: 0, write_bytes: 0,
  }],
  steps_declared: 1, steps_finished: 1,
};

const PAGE = {
  events: [
    { seq: 0, kind: "started", at_ms: 1787517649000 },
    { seq: 1, kind: "process_completed", at_ms: 1787517650000,
      trace: { process: "TRIMGALORE", status: "COMPLETED", name: "TRIMGALORE (test)",
               realtime_ms: 643 } },
  ],
  cursor: 1,
  stream_id: "1787517650000-0",
};

/** Every socket the page opens, so a test can assert what it was asked for and push to it. */
const sockets: FakeSocket[] = [];

class FakeSocket {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    sockets.push(this);
    queueMicrotask(() => this.onopen?.());
  }
  close() {
    this.closed = true;
  }
}

/** `view` is a parameter now, because the console is no longer what the page opens on — W2
 *  Task 6. A test about the socket has to say so rather than relying on the landing view. */
/** The envelope's body. **Every run screen fetches it now**, and a fallthrough mock handing
 *  this route a `RunState` is what made six graph tests fail at once — the panel read
 *  `curves` off a shape that has none. Empty is the honest fixture here: these tests are
 *  about the graph, and an empty series draws no panel. */
const SERIES = { curves: [], from_ms: 0, to_ms: 0, bin_ms: 1,
                 open: false, reported_resources: false };

function at(state: unknown = STATE, page: unknown = PAGE, view = "console",
            overview: unknown = OVERVIEW) {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const body = url.includes("/series") ? SERIES
      : url.includes("/events") ? page
      : url.includes("/overview") ? overview
      : state;
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  const router = createMemoryRouter(routes, {
    initialEntries: [`/runs/4c1e9a07b2f1de40?view=${view}`],
  });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("pages the record before it subscribes, and subscribes from where the page ended", async () => {
  at();
  await screen.findByTestId("console");
  await waitFor(() => expect(sockets).toHaveLength(1));
  // **The whole of §7.2 in one assertion.** Subscribing from zero replays what the page just
  // drew; subscribing from `$` drops whatever arrived between the two requests.
  expect(sockets[0].url).toContain(`from=${encodeURIComponent(PAGE.stream_id)}`);
});

it("draws the paged events before anything arrives on the socket", async () => {
  at();
  expect(await screen.findByTestId("event-1")).toHaveTextContent("TRIMGALORE");
});

it("appends what the socket sends without redrawing what it already has", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));

  sockets[0].onmessage?.({ data: JSON.stringify({
    seq: 2, kind: "process_completed", at_ms: 1787517651000,
    trace: { process: "STAR_ALIGN", status: "COMPLETED", name: "STAR_ALIGN (test)",
             realtime_ms: 29423 } }) });
  expect(await screen.findByTestId("event-2")).toHaveTextContent("STAR_ALIGN");

  // The same event again — a reconnect can redeliver — must not draw a second row.
  sockets[0].onmessage?.({ data: JSON.stringify({
    seq: 2, kind: "process_completed", at_ms: 1787517651000,
    trace: { process: "STAR_ALIGN", status: "COMPLETED", name: "STAR_ALIGN (test)",
             realtime_ms: 29423 } }) });
  expect(screen.getAllByTestId("event-2")).toHaveLength(1);
});

it("does not reopen a socket for a run the server says is over", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));
  sockets[0].onclose?.({ code: 1000 });   // drained and terminal
  await new Promise((r) => setTimeout(r, 20));
  expect(sockets).toHaveLength(1);
});

it("re-pages when the connection drops, rather than reopening blind", async () => {
  at();
  await waitFor(() => expect(sockets).toHaveLength(1));
  sockets[0].onclose?.({ code: 1006 });   // the connection went away
  await waitFor(() => expect(sockets).toHaveLength(2));
  const paged = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
  expect(paged.filter((u) => u.includes("/events")).length).toBeGreaterThan(1);
});

it("offers cancel on a live run, and does not on one that has ended", async () => {
  // **This replaces a test asserting `read-only until W4`.** That was true for as long as
  // nothing could act on a run; `cancel` is the first verb (`wiener.md` §11) and the promise
  // came down with it. A stale reassurance is worse than none.
  at({ ...STATE, phase: "running" }, PAGE, "overview");
  expect(await screen.findByTestId("cancel-run")).toBeInTheDocument();
});

it("does not offer cancel on a run that has already ended", async () => {
  // Refused server-side too — `409`, with the phase named. The control is absent because a
  // button that is always refused is a worse answer than no button.
  at({ ...STATE, phase: "succeeded" }, PAGE, "overview");
  await screen.findByTestId("run-panels");
  expect(screen.queryByTestId("cancel-run")).toBeNull();
});

it("opens on the run itself, and the console is not on it", async () => {
  // **W2's ending condition, and the bands make it stronger.** §18: you can read a 400-task
  // run without reading text — which is a statement that the console cannot be what the page
  // opens on. It was a tab; now it is a separate view reached from the tasks band, so the
  // claim is no longer *the console is not selected* but *the console is not here*.
  at(STATE, PAGE, "overview");
  expect(await screen.findByTestId("run-panels")).toBeInTheDocument();
  expect(screen.getByTestId("band-processes")).toBeInTheDocument();
  expect(screen.getByTestId("band-tasks")).toBeInTheDocument();
  expect(screen.queryByTestId("console")).toBeNull();
});

it("draws every band at once rather than one behind each of four tabs", async () => {
  // **The artboard is one scrolling page and this asserts it is not four.** `page-5`: *summary
  // top, trend middle, granular detail bottom*, and *drill down IN PLACE — never a second page
  // for the same run*. A tab IS a second page, and there were four.
  //
  // This test replaces one that asserted four enabled tab buttons. That test was true of the
  // screen it was written for and is the reason this one names bands rather than controls.
  at(STATE, PAGE, "overview");
  for (const band of ["run-panels", "band-processes", "band-tasks"]) {
    expect(await screen.findByTestId(band)).toBeInTheDocument();
  }
});

it("keeps table and graph as state on one band, not as two screens", async () => {
  // The artboard names this pair explicitly: *"THE TABLE/GRAPH TOGGLE IS STATE, NOT A SECOND
  // SCREEN. It was two artboards and that was two chances to drift — one board carries both."*
  at(STATE, PAGE, "overview");
  expect(await screen.findByTestId("board-table")).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByTestId("board-graph")).toHaveAttribute("aria-pressed", "false");
});


it("draws progress over steps the artifact declared, never over tasks seen", async () => {
  // §5. Nextflow discovers tasks as channels emit, so a task denominator GROWS and a
  // percentage over it goes backwards. The artifact's step count is known at t=0.
  at(STATE, PAGE, "overview", {
    steps_declared: 5, steps_finished: 3,
    rows: [{ ...OVERVIEW.rows[0], tasks: 28, done: 8, running: 20 }],
  });
  // **It moved from the header into the PROGRESS panel** and the claim is unchanged: the
  // denominator is the artifact's, never the 28 tasks Nextflow has discovered so far. The
  // header carried its own bar until the bands landed, and two of them said the same thing.
  const panel = await screen.findByTestId("panel-progress");
  expect(panel).toHaveTextContent("3");
  expect(panel).toHaveTextContent("of 5");
  expect(panel).not.toHaveTextContent("28");
});

it("says nothing about steps when the artifact could not be read", async () => {
  // A192's other half, drawn. `steps_declared: 0` means the directory is gone, and a bar
  // over a denominator of zero would be an invented number where there is no fact.
  //
  // **The panel is still drawn and it is the dash that carries the claim** — `page-5`: *"AN
  // ABSENT SERIES IS A REASON TO DRAW A DIFFERENT PANEL, NOT AN EMPTY ONE"*, and *"A DASH
  // NEVER MEANS ZERO"*. Dropping the panel would drop a question; drawing `0 of 0` would
  // invent an answer.
  at(STATE, PAGE, "overview", { steps_declared: 0, steps_finished: 0, rows: OVERVIEW.rows });
  const panel = await screen.findByTestId("panel-progress");
  expect(panel).toHaveTextContent("\u2014");
  expect(panel).not.toHaveTextContent("of 0");
});

it("reads the run the URL names, not the one the projection learned from an event", async () => {
  // **`RunState.run_id` is `""` until the first event lands**, which is every run between
  // launch and its first task — and the page passed it to every panel. The overview asked
  // `/api/runs//overview`, got a 404, and drew that under a header reading `run ` with no id.
  //
  // Asserting the *URLs* rather than the rendering is what makes this fail against the
  // defect: the fixture mock answers any path, so a panel handed an empty id still renders.
  at({ ...STATE, run_id: "" }, PAGE, "overview");

  await screen.findByRole("heading");
  const asked = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls.map(
    ([url]) => url,
  );
  // The cause before the symptom: a panel handed an empty id asks a URL with a hole in it.
  expect(asked.some((url) => url.includes("/overview"))).toBe(true);
  expect(asked.filter((url) => url.includes("/runs//"))).toEqual([]);
  expect(screen.getByRole("heading")).toHaveTextContent("run 4c1e9a07");
});

it("shows the pipeline's name when it has one, and keeps the id beside it", async () => {
  // **Plan 6 phase 2.** `PipelineDraft.name` has existed since 3E and nothing carried it across
  // the courier, so a run header read `run aa11bb22` while the builder two tabs away called the
  // same thing by a name somebody chose. The id stays visible: it is what a person pastes into
  // a message, and two runs of one pipeline share a name.
  at({ ...STATE, name: "rnaseq-counts" }, PAGE, "overview");
  expect(await screen.findByRole("heading")).toHaveTextContent("rnaseq-counts");
  expect(screen.getByRole("heading").parentElement).toHaveTextContent("4c1e9a07");
});

it("falls back to the id rather than inventing a name", async () => {
  // An artifact uploaded by hand — `curl -F bundle=@run.zip` — has no name, and that is
  // invariant 13's customer rather than a degraded one. **Never a name derived from the
  // digest**: a reader cannot tell one nobody chose from one somebody did.
  at({ ...STATE, name: "" }, PAGE, "overview");
  expect(await screen.findByRole("heading")).toHaveTextContent("run 4c1e9a07");
});
