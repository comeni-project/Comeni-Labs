import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";

/** The three Registry screens, against the shapes their endpoints actually answer.
 *
 * **Every fixture here is a `components["schemas"]` shape by hand**, which is the one place a
 * frontend test can drift from the API without `tsc` noticing — so the assertions are about
 * what a person can *do* with what is on screen rather than about the markup that carries it.
 */

const OVERVIEW = {
  sources: [
    {
      source: "nf-core",
      discovered: 1400,
      adaptable: 1200,
      adapted: 300,
      current: 280,
      outdated: 20,
      in_progress: 3,
      unsupported: 200,
      last_synced_at: "2026-09-05T09:00:00Z",
      snapshot_stale: false,
      sync_error: "",
    },
    {
      source: "pegi3s",
      discovered: 190,
      adaptable: 150,
      adapted: 0,
      current: 0,
      outdated: 0,
      in_progress: 0,
      unsupported: 40,
      last_synced_at: null,
      snapshot_stale: true,
      sync_error: "MF0200: the source refused to list its tools",
    },
  ],
  stages: {
    scaffolding: 1,
    queued: 2,
    generating: 1,
    validating: 0,
    review: 4,
    changes_requested: 1,
    failed: 2,
  },
  ai_lane: { concurrency: 1, active: 1, waiting: 2, oldest_wait_seconds: 900 },
  attention: {
    failed_syncs: 1,
    failed_adaptations: 2,
    stale_review_count: 1,
    outdated_count: 20,
  },
};

function item(over: Record<string, unknown> = {}) {
  return {
    id: "aa11",
    source: "pegi3s",
    ref: "prodigal",
    display_name: "prodigal",
    summary: "Predicts protein-coding genes in bacterial and archaeal genomes.",
    homepage_url: null,
    documentation_url: null,
    repository_url: null,
    licence: ["GPL-3.0"],
    keywords: [],
    categories: [],
    maintainers: ["pegi3s consortium"],
    latest_version: "2.6.3",
    container_refs: [],
    source_revision: "",
    content_digest: "d1",
    last_updated_at: null,
    input_hints: [],
    output_hints: [],
    classifications: [],
    source_facts: [],
    capabilities: {},
    adaptable: true,
    unsupported_reason: null,
    evidence: [],
    ...over,
  };
}

const CATALOGUE = {
  rows: [
    { item: item(), standing: { freshness: "unadapted" } },
    {
      item: item({ id: "bb22", ref: "fastqc", display_name: "fastqc", source: "nf-core" }),
      standing: {
        freshness: "in_progress",
        adaptation_id: "ad-1",
        adaptation_state: "generating",
      },
    },
  ],
  total: 2,
};

function row(over: Record<string, unknown> = {}) {
  return {
    id: "ad-1",
    catalogue_item_id: "bb22",
    source: "nf-core",
    ref: "fastqc",
    display_name: "fastqc",
    state: "generating",
    row_version: 1,
    who: "someone",
    failed_stage: null,
    current_revision_id: null,
    created_at: "2026-09-05T09:00:00Z",
    updated_at: "2026-09-05T09:00:00Z",
    ...over,
  };
}

const WORK = {
  items: [
    row(),
    row({ id: "ad-2", state: "queued", ref: "salmon", display_name: "salmon" }),
    row({ id: "ad-3", state: "review", ref: "star", display_name: "star" }),
    row({
      id: "ad-4",
      state: "failed",
      ref: "bwa",
      display_name: "bwa",
      failed_stage: "generating",
    }),
  ],
  next_cursor: null,
};

/** Routes a request by path, so a screen that makes three of them is not given one body. */
function serve(answers: Record<string, unknown>) {
  const fetcher = vi.fn(async (url: string) => {
    for (const [fragment, body] of Object.entries(answers)) {
      if (url.includes(fragment)) return { ok: true, status: 200, json: async () => body };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

function at(path: string) {
  // The router is returned rather than read off `window.location`: a memory router never
  // touches it, so an assertion there passes on an empty string whatever the page did.
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => vi.unstubAllGlobals());

describe("the registry overview", () => {
  it("counts and never lists", async () => {
    // **`forge-review.md` §3.** An Overview page was designed and CUT for answering the same
    // question as the queue, so the moment a tool ref or an adaptation id appears on this
    // screen it has become the page that was cut. The service holds the line and so does this.
    serve({ "/forge/overview": OVERVIEW });
    at("/forge");
    await screen.findByText(/Keep the tool catalogue supplied/);
    expect(screen.queryByText(/fastqc/)).toBeNull();
    expect(screen.queryByText(/ad-1/)).toBeNull();
  });

  it("makes every source segment a filter somebody can follow", async () => {
    // A number a person cannot follow is a number they re-find by hand. The link has to carry
    // BOTH the source and the freshness, or the destination answers a wider question than the
    // figure that was clicked.
    serve({ "/forge/overview": OVERVIEW });
    at("/forge");
    const outdated = await screen.findByRole("link", { name: /20 outdated/ });
    expect(outdated.getAttribute("href")).toBe("/forge/catalogue?source=nf-core&status=outdated");
  });

  it("says the AI lane's capacity beside what it is doing", async () => {
    // *1 active* on its own reads as *barely busy*. The waiting tail is what makes a
    // single-slot lane understandable rather than mysterious.
    serve({ "/forge/overview": OVERVIEW });
    at("/forge");
    expect(await screen.findByText(/capacity 1 · 2 waiting/)).toBeTruthy();
  });

  it("reports a failed sync by its code and offers the one action that answers it", async () => {
    // **MI0104**: the stored code, never upstream's message. A provider's error text can carry
    // a URL or a token fragment, and this is the front door.
    serve({ "/forge/overview": OVERVIEW });
    at("/forge");
    expect(await screen.findByText(/MF0200/)).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Retry" }).length).toBeGreaterThan(0);
  });

  it("says what to do when nothing has been synced", async () => {
    // An empty registry is a first-run state, and naming the action that ends it is more use
    // than reporting that a list is empty.
    serve({
      "/forge/overview": {
        ...OVERVIEW,
        sources: [],
        attention: { ...OVERVIEW.attention, outdated_count: 0 },
      },
    });
    at("/forge");
    expect(await screen.findByText("No source has been read yet.")).toBeTruthy();
  });
});

describe("the catalogue", () => {
  it("asks the server for the filter rather than filtering the page", async () => {
    // **Filtering after paging reports *11 of 1,612***, the total describing the catalogue and
    // the rows describing one page of it. The assertion is on the request, because that is
    // where the two implementations differ — the rendered table looks the same either way.
    const fetcher = serve({ "/forge/catalogue": CATALOGUE });
    at("/forge/catalogue?status=outdated&source=pegi3s");
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const asked = fetcher.mock.calls.map(([url]) => String(url)).join(" ");
    expect(asked).toContain("status=outdated");
    expect(asked).toContain("source=pegi3s");
  });

  it("offers Adapt for a tool with no adaptation and Open for one already moving", async () => {
    // `begin` refuses a second active adaptation, so a row that offered *Adapt* on a tool
    // already in flight would be a button whose only outcome is a refusal.
    serve({ "/forge/catalogue": CATALOGUE });
    at("/forge/catalogue");
    await screen.findByText("prodigal");
    expect(screen.getByRole("button", { name: "Adapt" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe(
      "/forge/adaptations/ad-1",
    );
  });

  it("says which stage an in-progress tool is at", async () => {
    // *In progress* covers five states, and which one is exactly the reviewer's question.
    serve({ "/forge/catalogue": CATALOGUE });
    at("/forge/catalogue");
    expect(await screen.findByText("generating")).toBeTruthy();
  });

  it("opens the inspector from the URL, on a tool the page need not contain", async () => {
    // A `?tool=` link may be opened under a different filter or offset — a colleague's link,
    // a bookmark — so the panel fetches by id rather than reading a visible row.
    serve({
      "/forge/catalogue/aa11": item(),
      "/forge/catalogue": { rows: [], total: 0 },
    });
    at("/forge/catalogue?tool=aa11");
    const panel = await screen.findByRole("complementary");
    expect(await within(panel).findByText(/Predicts protein-coding genes/)).toBeTruthy();
  });

  it("says which filter emptied the result", async () => {
    // "No tools" on a screen with four controls set is an answer nobody can act on.
    serve({ "/forge/catalogue": { rows: [], total: 0 } });
    at("/forge/catalogue?q=nothing&status=outdated");
    expect(await screen.findByText("Nothing matches.")).toBeTruthy();
    expect(screen.getByText(/search “nothing”/)).toBeTruthy();
  });

  it("writes a chip into the URL so the view can be sent to somebody", async () => {
    serve({ "/forge/catalogue": CATALOGUE });
    const router = at("/forge/catalogue");
    await screen.findByText("prodigal");
    await userEvent.click(screen.getByRole("button", { name: "Outdated" }));
    await waitFor(() => expect(router.state.location.search).toContain("status=outdated"));
  });
});

describe("the work queue", () => {
  it("draws the lane as one slot with its waiting tail", async () => {
    // Capacity is one. A queue that showed only the held row would make the position of
    // everything behind it unknowable, which is the number people actually want.
    serve({ "/forge/adaptations": WORK });
    at("/forge/work");
    expect(await screen.findByText(/position 2 · approximate/)).toBeTruthy();
  });

  it("keeps what a person acts on out of what a worker holds", async () => {
    // One table ordered by `updated_at` interleaves them, so the two rows waiting on a human
    // sit between six the machine is still working on.
    serve({ "/forge/adaptations": WORK });
    at("/forge/work");
    expect(await screen.findByText("Ready for review (1)")).toBeTruthy();
    expect(screen.getByText("Failed (1)")).toBeTruthy();
  });

  it("renders an empty band rather than dropping it", async () => {
    // A reader cannot tell a band with nothing in it from a band that failed to load, and
    // dropping one is how a screen quietly stops answering a question.
    serve({ "/forge/adaptations": { items: [], next_cursor: null } });
    at("/forge/work");
    expect(await screen.findByText("Nothing is waiting on a person.")).toBeTruthy();
    expect(screen.getByText("The lane is idle.")).toBeTruthy();
  });

  it("asks why before retrying, because the answer outlives the click", async () => {
    // A retry writes an event somebody reads six months later, and "retried from the work
    // queue" says nothing the timestamp beside it did not.
    serve({ "/forge/adaptations": WORK });
    at("/forge/work?band=failed");
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(screen.getByLabelText("Why retry bwa")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Go" }).hasAttribute("disabled")).toBe(true);
  });

  it("filters to one band from the URL", async () => {
    serve({ "/forge/adaptations": WORK });
    at("/forge/work?band=review");
    await screen.findByText("Ready for review (1)");
    expect(screen.queryByText("Failed (1)")).toBeNull();
  });
});
