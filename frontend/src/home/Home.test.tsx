import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** The front door — **the lab's work**, and the rules that keep it from becoming a dashboard.
 *
 * These replace the landing page's tests wholesale. That page had a hero, a tagline, two calls
 * to action pointing at the now-hidden forge, and a `standing` block reporting what the REGISTRY
 * holds — which `ov-settled` cuts in one line: *that is the PRODUCT's state, not YOURS.*
 */

const PIPELINE = {
  id: "aaaa1111", name: "rnaseq-counts", who: "R. Correia",
  updated_at: "2026-08-29T10:00:00Z", steps: 4, makes: ["counts.matrix"],
  kept: true, digest: "sha256:" + "a".repeat(64),
  provenance: { settled: 9, measured: 1, open: 1, by_person: 4, by_model: 0 },
  open_values: [{ step: "align", setting: "seq_platform" }],
  open_not_named: 0,
};

const SETTLED = {
  ...PIPELINE, id: "bbbb2222", name: "wgs-variants", who: "J. Costa",
  makes: ["variants.vcf"],
  digest: "sha256:" + "b".repeat(64),
  provenance: { settled: 12, measured: 2, open: 0, by_person: 0, by_model: 0 },
  open_values: [], open_not_named: 0,
};

const RUNNING = {
  id: "cccc3333", phase: "running", executor: "local", submitted_by: "operator",
  submitted_at: "2026-08-30T09:00:00Z", ended_at: null,
  tasks_done: 9, tasks_seen: 24, pipeline_digest: PIPELINE.digest,
};

const FINISHED = {
  ...RUNNING, id: "dddd4444", phase: "succeeded",
  ended_at: "2026-08-30T09:22:00Z", tasks_done: 4, tasks_seen: 4,
  pipeline_digest: SETTLED.digest,
};

/** Route each request to the half that owns it — the page reads three sources and joins them
 *  in the browser, which is the whole point of `wiener.md` §12. */
function at({ drafts = [PIPELINE, SETTLED], runs = [RUNNING, FINISHED], mendel = [] as unknown[] }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const body = url.includes("/attention") ? { forge: [], mendel }
      : url.includes("/pipeline/drafts") ? { drafts, total: drafts.length }
      : url.includes("/api/runs") ? { runs, total: runs.length }
      : {};
    return { ok: true, status: 200, json: async () => body };
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/"] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the front door", () => {
  it("leads with the lab's pipelines rather than the registry's inventory", async () => {
    at({});
    await waitFor(() => expect(screen.getAllByText("rnaseq-counts").length).toBeGreaterThan(0));
    expect(screen.getByText("counts.matrix")).toBeTruthy();
    // The NOW band names a run by its PIPELINE, not by its id — a run id is how the machine
    // addresses it, and what a reader recognises is what it is a run of.
    expect(screen.getAllByText("rnaseq-counts").length).toBe(2);
    expect(screen.getByRole("link", { name: "New pipeline" })).toBeTruthy();
  });

  it("is SHORTER when nothing is happening, not filled with a reassurance", async () => {
    // **The phase's central guard.** `ov-absence`: the difference between the ACTIVE and QUIET
    // artboards is not a different empty state, it is that the NOW band DOES NOT EXIST. No
    // card, no "nothing is waiting on you", no "the instance is idle" — the page is just
    // shorter.
    //
    // The instinct to fill an empty region with a reassuring sentence is exactly what made the
    // old page read as generated, and it is the single thing most likely to be quietly undone.
    at({ runs: [FINISHED], mendel: [] });
    await waitFor(() => expect(screen.getByText("wgs-variants")).toBeTruthy());

    expect(screen.queryByText(/running now/i)).toBeNull();
    expect(screen.queryByText(/waiting on a person/i)).toBeNull();
    expect(screen.queryByText(/nothing is waiting/i)).toBeNull();
    expect(screen.queryByText(/idle/i)).toBeNull();
  });

  it("renders the NOW band when something is actually happening", async () => {
    at({ runs: [RUNNING, FINISHED] });
    await waitFor(() => expect(screen.getByText(/running now/i)).toBeTruthy());
    expect(screen.getByText("9 of 24 tasks")).toBeTruthy();
  });

  it("NAMES the values waiting on a person rather than counting them", async () => {
    // *"strandedness and fragment size"*, not *"2 items"* — `ov-settled`. A count is what you
    // write when you have not looked, and the sentence is composed server-side so the page
    // cannot quietly turn it back into a number.
    at({
      mendel: [{
        what: "rnaseq-counts: seq_platform has no rule",
        where: "/build?draft=aaaa1111", count: 1, urgency: "waiting",
      }],
    });
    await waitFor(() => expect(screen.getByText(/waiting on a person/i)).toBeTruthy());
    expect(screen.getByText(/seq_platform has no rule/)).toBeTruthy();
    expect(screen.queryByText(/1 item/)).toBeNull();
  });

  it("never renders a registry subject", async () => {
    // **The narrowed rule that survived.** `forge-review.md` §3 cut an Overview page once for
    // answering the Queue's question, and the operator lifted that constraint on 2026-08-30 —
    // this page renders pipelines and runs. What it may still never render is a CONTRACT id, a
    // question subject or a drift row; the moment one appears it has become the page that was
    // cut. §3 records the lift so nobody re-applies the old rule by finding it.
    at({});
    await waitFor(() => expect(screen.getAllByText("rnaseq-counts").length).toBeGreaterThan(0));
    expect(document.body.textContent).not.toMatch(/nf-core\//);
    expect(document.body.textContent).not.toMatch(/@\d+\.\d+\.\d+/);
    expect(document.body.textContent).not.toMatch(/drift/i);
  });

  it("keeps a pipeline's readiness apart from a run's history", async () => {
    // `ov-work`: the actual bug behind two blocks reading as one list rendered twice was RUN
    // information leaking onto PIPELINE rows — *"last run 2d ago · M. Silva"*. By-pipeline is
    // readiness; by-run is history; they are two objects and never one.
    //
    // **Scoped to the pipeline table, and it used to scan the whole page.** The NOW band says
    // `operator · started 21m ago` about a RUN, which is the artboard's own copy and exactly
    // the information this rule is happy to see — on a run. A page-wide scan called that a
    // leak, which is the third guard in two days to fire on something it exists to permit.
    // Scoping it also makes it stronger: it can no longer be satisfied by the word being
    // absent from somewhere else.
    at({});
    await waitFor(() => expect(screen.getAllByText("rnaseq-counts").length).toBeGreaterThan(0));
    const readiness = within(screen.getByRole("table"));
    expect(readiness.queryByText(/ago/)).toBeNull();
    expect(screen.getByText("1 open")).toBeTruthy();
  });

  it("shows an unkept pipeline no provenance rather than three zeroes", async () => {
    // Absent, not zero. A bar of empty segments claims a pipeline with nothing open, which is
    // the opposite of *nobody has looked*.
    const unkept = {
      ...PIPELINE, id: "eeee5555", name: "draft-only", kept: false, digest: null,
      provenance: null, makes: [], open_values: [], open_not_named: 0,
    };
    at({ drafts: [unkept], runs: [] });
    await waitFor(() => expect(screen.getByText("draft-only")).toBeTruthy());
    expect(screen.getByText("not kept")).toBeTruthy();
  });

  it("offers the first-run composition when the lab has nothing yet", async () => {
    at({ drafts: [], runs: [] });
    await waitFor(() => expect(screen.getByText("What do you want to make?")).toBeTruthy());
    // **The prompt is drawn and disabled, with the reason under it** — door 1 is declared by
    // invariant 3 and implemented nowhere, and the operator chose to show what is coming rather
    // than omit it. What must never happen is it appearing to work.
    expect(screen.getByPlaceholderText(/RNA-seq/)).toBeDisabled();
    expect(screen.getByText(/not built yet/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /build it by hand/i })).toBeTruthy();
  });

  it("still lists the lab's pipelines when Wiener is unreachable", async () => {
    // The two halves are independent by design. A laboratory reading what it has built does not
    // need the execution half to be up, and a page that 500s because one of two servers is down
    // would make them one server in practice.
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/api/runs")) throw new Error("connection refused");
      const body = url.includes("/attention") ? { forge: [], mendel: [] }
        : { drafts: [PIPELINE], total: 1 };
      return { ok: true, status: 200, json: async () => body };
    }));
    render(
      <QueryClientProvider client={makeClient()}>
        <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/"] })} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getAllByText("rnaseq-counts").length).toBeGreaterThan(0));
    expect(screen.getByText(/Run history is unavailable/)).toBeTruthy();
  });
});
