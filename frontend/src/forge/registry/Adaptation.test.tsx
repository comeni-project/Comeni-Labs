import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";

/** One route, every state — §8.4 and §8.5.
 *
 * **The assertions are about what a reviewer can do and be told**, not about markup: whether a
 * proposal is distinguishable from a source fact, whether a disabled button says why, whether
 * asking a question can change a file. Those are the claims the page exists to make.
 */

function row(over: Record<string, unknown> = {}) {
  return {
    id: "ad-1",
    catalogue_item_id: "bb22",
    source: "nf-core",
    ref: "samtools/sort",
    display_name: "samtools/sort",
    state: "review",
    row_version: 3,
    who: "rafael",
    failed_stage: null,
    current_revision_id: "rev-2",
    created_at: "2026-09-05T09:00:00Z",
    updated_at: "2026-09-05T09:40:00Z",
    ...over,
  };
}

function detail(over: Record<string, unknown> = {}) {
  return {
    adaptation: row(),
    revisions: [
      {
        id: "rev-2",
        ordinal: 2,
        state: "validated",
        green: true,
        unresolved_required: 0,
        validation: { ran: true, diagnostics: [] },
        created_at: "2026-09-05T09:30:00Z",
      },
    ],
    events: [
      {
        kind: "generated",
        from_state: "generating",
        detail: "revision 2 written",
        actor: "worker:abc",
        at: "2026-09-05T09:30:00Z",
      },
    ],
    ...over,
  };
}

const CANDIDATE = {
  adaptation_id: "ad-1",
  graph: {
    process: "SAMTOOLS_SORT",
    consumes: [
      {
        channel: "bam",
        name: "bam",
        type_id: "alignment.bam",
        states: ["unsorted"],
        origin: "derived",
        hole_id: "consumes.bam.type_id",
      },
    ],
    produces: [
      {
        channel: "sorted",
        name: "sorted",
        type_id: "alignment.bam",
        states: ["coordinate_sorted"],
        origin: "model",
        hole_id: "produces.sorted.state",
      },
    ],
    params: 3,
  },
  fields: [
    {
      field: "consumes[0].type_id",
      hole_id: "consumes.bam.type_id",
      value: '"alignment.bam"',
      how: "derived",
      by: "nf-core",
      why: "read from meta.yml",
      evidence_ids: ["E004"],
    },
    {
      field: "produces[0].state",
      hole_id: "produces.sorted.state",
      value: '["coordinate_sorted"]',
      how: "model",
      by: "claude-opus-5",
      why: "sort with no -n orders by coordinate",
      evidence_ids: [],
    },
  ],
  holes: [],
  evidence: [
    {
      id: "E004",
      excerpt: { locator: "meta.yml:12", text: "input BAM file" },
      kind: "metadata",
    },
  ],
  files: [{ path: "main.nf", text: "process SAMTOOLS_SORT {\n}\n", authored: false }],
  origins: { derived: 1, model: 1, human: 0, open: 0 },
  source_digest: "7be1aaaa",
};

/** Route a request by the END of its path, and 404 anything the map does not name.
 *
 * **`includes` is the wrong test, and getting there cost three rounds.**
 * `/api/forge/adaptations/ad-1` is a prefix of `.../ad-1/candidate`, so a substring router
 * hands the candidate request the detail body — the page then renders *nothing has been
 * scaffolded* against a fixture that has one, or crashes on a field the wrong body lacks.
 * Matching the *longest* fragment inverts the bug rather than fixing it, because
 * `/adaptations/ad-1` is the longer string.
 *
 * Matching the path's tail is what actually distinguishes a resource from its sub-resource,
 * and it makes an unnamed endpoint a 404 — which is what several of these tests are about.
 */
function serve(answers: Record<string, unknown>) {
  // `init` is declared even though the happy path ignores it: the stale-mutation tests read
  // `method` off the recorded calls, and a one-argument signature makes that a type error.
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    void init;
    const path = String(url).split("?")[0];
    for (const [fragment, body] of Object.entries(answers)) {
      if (path.endsWith(fragment)) return { ok: true, status: 200, json: async () => body };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

function reviewing(over: Record<string, unknown> = {}) {
  return serve({
    "/candidate": CANDIDATE,
    "/approval": { can_approve: true, refusals: [] },
    "/messages": [],
    "/adaptations/ad-1": detail(),
    ...over,
  });
}

function at(path = "/forge/adaptations/ad-1") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => vi.unstubAllGlobals());

describe("one route, every state", () => {
  it("draws the stage track while the adaptation is still being built", async () => {
    // §8.4: queue position and the named stage, on the same URL the review screen uses. A
    // second route would redirect somebody mid-sentence the moment generation finished.
    serve({
      "/candidate": { ...CANDIDATE, holes: [] },
      "/adaptations/ad-1": detail({ adaptation: row({ state: "generating" }) }),
      "/messages": [],
    });
    at();
    expect(await screen.findByText("Analyse")).toBeTruthy();
    expect(screen.getByText("Implement")).toBeTruthy();
    // The chat rail belongs to review: there is no revision to ground an answer on yet.
    expect(screen.queryByLabelText("Ask about this revision")).toBeNull();
  });

  it("says nothing has been scaffolded rather than showing an empty candidate", async () => {
    // A 404 from `/candidate` is an ordinary state — an adaptation in `scaffolding` has none —
    // and an empty one would read as *the scaffold produced nothing*.
    serve({
      "/adaptations/ad-1": detail({ adaptation: row({ state: "scaffolding" }) }),
      "/messages": [],
    });
    at();
    expect(await screen.findByText("Nothing has been scaffolded yet.")).toBeTruthy();
  });

  it("shows durable events and never a streamed thought", async () => {
    serve({
      "/adaptations/ad-1": detail({ adaptation: row({ state: "generating" }) }),
      "/candidate": CANDIDATE,
      "/messages": [],
    });
    at();
    expect(await screen.findByText("revision 2 written")).toBeTruthy();
    expect(screen.getByText(/intermediate reasoning is not streamed/)).toBeTruthy();
  });
});

describe("the review screen", () => {
  it("tells a model's proposal from a source fact on the graph", async () => {
    // **The single failure a review exists to catch.** The origin has to reach the port, or the
    // graph draws a guess and a read fact identically.
    reviewing();
    at();
    const sorted = await screen.findByTitle("AI proposed");
    expect(within(sorted).getByText("alignment.bam")).toBeTruthy();
    expect(screen.getByTitle("from the source")).toBeTruthy();
  });

  it("opens the field, its rationale and its evidence when a port is selected", async () => {
    // §8.5: *selecting a port opens the exact contract field, evidence, rationale, and source
    // locator*. One panel, because they are one question.
    reviewing();
    at();
    await userEvent.click(await screen.findByTitle("from the source"));
    expect(await screen.findByText(/read from meta.yml/)).toBeTruthy();
    expect(screen.getByText(/meta.yml:12/)).toBeTruthy();
  });

  it("puts the selection in the URL so a reviewer can send it", async () => {
    reviewing();
    const router = at();
    await userEvent.click(await screen.findByTitle("AI proposed"));
    await waitFor(() =>
      expect(router.state.location.search).toContain("at=produces.sorted.state"),
    );
  });

  it("opens the parameter table from the count on the process node", async () => {
    // A count that is not a control is a number a reviewer has to go and find.
    reviewing();
    at();
    await userEvent.click(await screen.findByText(/3 parameters/));
    expect(await screen.findByText("consumes[0].type_id: \"alignment.bam\"")).toBeTruthy();
  });

  it("says whether main.nf was copied or written", async () => {
    // A source that ships Nextflow gets a contract bound to its process and nothing downstream
    // may author one — so *which* is the rule being checked, and the pane has to say it.
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Files" }));
    expect(await screen.findByText(/copied unchanged/)).toBeTruthy();
  });

  it("counts open holes beside the settled origins", async () => {
    // A bar showing only what was decided makes a candidate with nine open holes look as
    // finished as one with none.
    reviewing();
    at();
    const row = await screen.findByText("proposed by the model", { exact: false });
    expect(row.textContent).toBe("1 proposed by the model");
    expect(screen.getByText("still open", { exact: false }).textContent).toBe("0 still open");
  });
});

describe("approval", () => {
  it("explains every blocking condition at once, before the button is pressed", async () => {
    // `approval_refusals` returns all six rather than the first: six clicks to learn six facts
    // the server knew at the first one. A disabled button whose reason is hidden in a dialog is
    // a disabled button with no reason.
    reviewing({
      "/approval": {
        can_approve: false,
        refusals: [
          "MF0301: the registry moved since this candidate was validated",
          "MF0301: 2 required hole(s) are still unresolved",
        ],
      },
    });
    at();
    const approve = await screen.findByRole("button", { name: "Approve and publish" });
    expect(approve.hasAttribute("disabled")).toBe(true);
    expect(await screen.findByText("Why approve is unavailable")).toBeTruthy();
    expect(screen.getByText(/2 required hole\(s\) are still unresolved/)).toBeTruthy();
  });

  it("keeps request-changes and approve as separate explicit actions", async () => {
    reviewing();
    at();
    expect(await screen.findByRole("button", { name: "Request changes" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve and publish" })).toBeTruthy();
  });

  it("requires a reason before it will publish", async () => {
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Approve and publish" }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Approve and publish" });
    expect(confirm.hasAttribute("disabled")).toBe(true);
    await userEvent.type(within(dialog).getByLabelText(/Why this is right/), "checked by hand");
    expect(confirm.hasAttribute("disabled")).toBe(false);
  });

  it("selects no rule candidate by default", async () => {
    // §8.5 and §5: a rule is scientific policy, not metadata. Approving the contract does not
    // accept any, and the default is what makes that true without anybody remembering.
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Approve and publish" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/No rule candidate is selected/)).toBeTruthy();
    expect(within(dialog).queryAllByRole("checkbox", { checked: true })).toEqual([]);
  });

  it("says request changes is not rejection, and what it actually does", async () => {
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/This is not rejection/)).toBeTruthy();
    expect(within(dialog).getByText(/you stay on this page/)).toBeTruthy();
  });

  it("closes a dialog on Escape", async () => {
    // §8.5's last box asks for the dialogs to be keyboard-tested, and this is the one behaviour
    // a person reaches for without being told it exists.
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("focuses the first field when a dialog opens", async () => {
    reviewing();
    at();
    await userEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(document.activeElement).toBe(within(dialog).getByLabelText(/What should change/)),
    );
  });
});

describe("a mutation that has gone stale", () => {
  it("shows the server's coded refusal rather than a friendlier sentence", async () => {
    // **The candidate moved under the reviewer**, which is the whole reason the API refuses on
    // a compare-and-swap rather than trusting the row it was told about. `MF0300` is what the
    // reviewer needs — a rewritten "something went wrong" would hide the one string that says
    // what happened and can be looked up.
    const fetcher = reviewing();
    fetcher.mockImplementation(async (url, init) => {
      if (init?.method === "POST") {
        return {
          ok: false,
          status: 422,
          json: async () => ({
            detail: "MF0300: review → publishing is not a legal move from changes_requested",
          }),
        };
      }
      const path = String(url).split("?")[0];
      if (path.endsWith("/candidate")) return { ok: true, status: 200, json: async () => CANDIDATE };
      if (path.endsWith("/approval"))
        return { ok: true, status: 200, json: async () => ({ can_approve: true, refusals: [] }) };
      if (path.endsWith("/messages")) return { ok: true, status: 200, json: async () => [] };
      return { ok: true, status: 200, json: async () => detail() };
    });

    at();
    await userEvent.click(await screen.findByRole("button", { name: "Approve and publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Why this is right/), "looks right");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve and publish" }));

    // `Refusal` renders the message AND the `forge explain` line, so both match — asserting
    // on one would be asserting that the other is absent, which is not the claim.
    expect((await within(dialog).findAllByText(/MF0300/)).length).toBeGreaterThan(0);
    // The dialog stays open: a refusal the reviewer cannot read is a refusal that did not
    // happen as far as they are concerned.
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("keeps request-changes open on a refusal too", async () => {
    const fetcher = reviewing();
    fetcher.mockImplementation(async (url, init) => {
      if (init?.method === "POST") {
        return { ok: false, status: 422, json: async () => ({ detail: "MF0300: not from here" }) };
      }
      const path = String(url).split("?")[0];
      if (path.endsWith("/candidate")) return { ok: true, status: 200, json: async () => CANDIDATE };
      if (path.endsWith("/approval"))
        return { ok: true, status: 200, json: async () => ({ can_approve: true, refusals: [] }) };
      if (path.endsWith("/messages")) return { ok: true, status: 200, json: async () => [] };
      return { ok: true, status: 200, json: async () => detail() };
    });

    at();
    await userEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/What should change/), "the state is a guess");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send back for changes" }));
    expect((await within(dialog).findAllByText(/MF0300/)).length).toBeGreaterThan(0);
  });
});

describe("a candidate sent back for changes", () => {
  it("keeps the review surface, because the candidate is kept", async () => {
    // §1.6: *request changes* is not rejection, and the previous candidate has to survive. A
    // page that dropped to the stage track would be showing the reviewer that their correction
    // threw the work away.
    reviewing({
      "/adaptations/ad-1": detail({ adaptation: row({ state: "changes_requested" }) }),
    });
    at();
    expect(await screen.findByText("Input / output")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Request changes" })).toBeTruthy();
  });
});

describe("the chat rail", () => {
  it("is read-only with respect to the candidate, and says so", async () => {
    // §8.5: the composer must not imply edits. `forge_review.py` moves no adaptation and
    // writes no file; this is that guarantee where a person can read it.
    reviewing();
    at();
    expect(await screen.findByText("asking does not change the candidate")).toBeTruthy();
    expect(screen.getByLabelText("Ask about this revision")).toBeTruthy();
  });

  it("shows a pending turn immediately rather than waiting for the answer", async () => {
    // §7: a curator who sees nothing until an answer arrives cannot tell *sent* from *lost*,
    // and at 227 seconds they retype it.
    reviewing({
      "/messages": [
        {
          id: 1,
          role: "curator",
          state: "pending",
          content: "Is the input really unsorted?",
          citations: [],
          revision_id: "rev-2",
          at: "2026-09-05T09:41:00Z",
        },
      ],
    });
    at();
    expect(await screen.findByText(/queued — waiting for the AI lane/)).toBeTruthy();
    expect(screen.getByText("Is the input really unsorted?")).toBeTruthy();
  });

  it("makes each cited claim clickable, and clicking one opens the evidence", async () => {
    reviewing({
      "/messages": [
        {
          id: 2,
          role: "assistant",
          state: "answered",
          content: "The meta.yml calls it an input BAM.",
          citations: [{ kind: "source_fact", evidence_id: "E004", file: "", line: null }],
          revision_id: "rev-2",
          at: "2026-09-05T09:42:00Z",
        },
      ],
    });
    at();
    await userEvent.click(await screen.findByRole("button", { name: "E004" }));
    expect(await screen.findByText(/meta.yml:12/)).toBeTruthy();
  });

  it("keeps the composer usable from the keyboard alone", async () => {
    const fetcher = reviewing();
    at();
    const box = await screen.findByLabelText("Ask about this revision");
    // **Enter sends.** A review question is usually one sentence, and a composer whose only
    // send is a mouse trip is one people stop using.
    await userEvent.type(box, "why coordinate order?{Enter}");
    await waitFor(() =>
      expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true),
    );
  });
});
