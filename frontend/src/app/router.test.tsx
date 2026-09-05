import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { routes } from "./router";

/** Mirrors `main.tsx`: the query client wraps the router, not the other way round.
 *
 * Without it the routes still mount and the ErrorBoundary catches "No QueryClient set" — a
 * green boundary over a broken tree, which is exactly the failure this phase exists to stop
 * shipping. `retry: false` so a failing fetch fails now rather than after three backoffs. */
function at(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("routing", () => {
  it("keeps you at / , because 3B built the landing page", async () => {
    // **This test used to assert the opposite**, and phase 0 wrote it that way on purpose:
    // `/` redirected to the queue for the whole of 3A because a placeholder home built then
    // would have been thrown away. 3B is what it was waiting for, so the assertion inverts
    // rather than disappearing — the redirect leaving is the deliverable.
    const router = at("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("keeps the shell mounted across navigation", async () => {
    at("/forge/catalogue");
    // The shell is in the layout route, so it must be present on a child route too.
    //
    // **Asserted on the wordmark, not on the `navigation` landmark.** There are two landmarks
    // on a Registry page since Task 10 — the global bar and the section subnav — and a bare
    // `getByRole("navigation")` throws on *finding both*, which is the design working. The
    // wordmark belongs to the shell and to nothing else.
    await waitFor(() => expect(screen.getByLabelText("Comeni — home")).toBeTruthy());
  });

  it("has no destination left to disable", () => {
    at("/forge/catalogue");
    // **The list reached zero, so the assertion inverts rather than disappearing** — the same
    // move `/`'s redirect test made when 3B built the landing page.
    //
    // Six dead `href="#"` links are what made slice 1 look finished. Every unbuilt destination
    // since has been `aria-disabled` and titled with the phase that builds it: `Contracts` became
    // real in phase 4, `Sources` in phase 6, `Tools` swallowed both in 3D, and `Builder` — the
    // last one — became a link in 3C phase 3. `Soon` is deleted rather than kept for a future
    // occupant, because a component with no caller is a component that rots.
    expect(document.querySelectorAll('[aria-disabled="true"]').length).toBe(0);
    expect(document.querySelectorAll('a[href="#"]').length).toBe(0);
  });

  it("advertises the Registry and none of the screens it replaces", async () => {
    // **The frame offered no way into the forge at all from 2026-08-30 to 2026-09-05**, which
    // was the operator's decision while the forge was deprecated and unmaintained. Its rework
    // is what changed the premise: `/forge` is now a built section, so it is advertised, and
    // this assertion inverts rather than disappearing — the same move `/`'s redirect test made.
    //
    // **What is still not advertised is every screen the rework replaces.** `/forge/queue` and
    // `/forge/tools` resolve and the next test holds that they do; a frame that linked to both
    // the new section and the old ones would be offering a person two registries.
    at("/build");
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
    const into = Array.from(screen.getByRole("navigation").querySelectorAll("a"))
      .map((a) => a.getAttribute("href") ?? "")
      .filter((href) => href.startsWith("/forge"));
    expect(into).toEqual(["/forge"]);
  });

  it.each([["/forge"], ["/forge/catalogue"], ["/forge/work"]])(
    "puts the section subnav below the frame on %s",
    async (path) => {
      // **Below, and never in it** — §8 says so twice. Three section links in the global bar
      // would make the Registry read as three workspaces rather than as one destination, and
      // the global bar is where a person picks which half of the product they are in.
      at(path);
      const sections = await screen.findByRole("navigation", { name: "Registry sections" });
      expect(
        Array.from(sections.querySelectorAll("a")).map((a) => a.getAttribute("href")),
      ).toEqual(["/forge", "/forge/catalogue", "/forge/work"]);
      expect(screen.queryByText("Something broke")).toBeNull();
    },
  );

  it.each([
    ["/forge/queue", "/forge/work"],
    ["/forge/tools", "/forge/catalogue"],
    ["/forge/sources", "/forge/catalogue"],
    ["/forge/contracts", "/forge/catalogue"],
  ])("sends %s to %s rather than 404ing it", async (from, to) => {
    // **The rework's last box, and it waited on purpose.** These four resolved through Tasks
    // 10 to 12 because the plan says *only after this walk*: a redirect installed before the
    // replacement had been driven end to end sends somebody from a screen that works to one
    // that does not.
    //
    // **Redirected, never 404ed.** These paths are in the operator's history, in `make dev`'s
    // banner and in four journal entries. A merged screen that breaks every saved link is a
    // merge that costs more than it gives.
    const router = at(from);
    await waitFor(() => expect(router.state.location.pathname).toBe(to));
    expect(screen.queryByText("Something broke")).toBeNull();
  });

  it.each([
    ["/forge/queue/question/consumes%5B0%5D.type_id"],
    ["/forge/contracts/nf-core/fastqc@0.12.1"],
  ])("keeps %s resolvable, because it addresses one object", async (path) => {
    // **The line the redirects stop at.** A question and a contract are addressed by an id in
    // the path, and there is nowhere in the new section that answers about the same object —
    // sending them to a list would turn a deep link into a shrug. They keep their screens
    // until the cleanup PR replaces them.
    const router = at(path);
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
    // Compared as given: react-router keeps the pathname percent-encoded, which is the whole
    // reason `/forge/contracts/*` is a splat — a contract id contains slashes and brackets.
    expect(router.state.location.pathname).toBe(path);
    // `ErrorBoundary` renders this heading and nothing else does — asserted on its own words
    // rather than on a testid, so the guard does not need the component to cooperate.
    expect(screen.queryByText("Something broke")).toBeNull();
  });

  it("puts a question's identity in the path so it can be linked", () => {
    const router = at("/forge/queue/question/consumes%5B0%5D.type_id");
    expect(router.state.location.pathname).toContain("consumes");
  });
});
