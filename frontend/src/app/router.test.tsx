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
    at("/forge/queue");
    // The nav is in the layout route, so it must be present on a child route too — that is
    // what makes the registry panel able to stay open across navigation. Asserted on the
    // landmark, not on the word "Forge": the design uses it twice, as the wordmark and as a
    // workspace tab, and both are right.
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
  });

  it("has no destination left to disable", () => {
    at("/forge/queue");
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

  it("offers no way into the forge from the frame", async () => {
    // **Hidden, not removed** — Plan 4 phase 0, operator's decision 2026-08-30. The forge is
    // carried as needing testing and rework, so the frame stops advertising it. This half of
    // the pair asserts the advertising is gone; the next one asserts the destinations are not.
    at("/build");
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
    const into = Array.from(screen.getByRole("navigation").querySelectorAll("a"))
      .map((a) => a.getAttribute("href") ?? "")
      .filter((href) => href.startsWith("/forge"));
    expect(into).toEqual([]);
  });

  it.each([
    ["/forge/queue"],
    ["/forge/tools"],
    ["/forge/queue/question/consumes%5B0%5D.type_id"],
    ["/forge/contracts/nf-core/fastqc@0.12.1"],
  ])("keeps %s resolvable after the tabs came out", async (path) => {
    // **The other half.** A route nobody can see is a route somebody deletes, and the operator,
    // `make dev`'s banner and three journal entries all still reach these by URL. The
    // `ErrorBoundary` is what a broken route renders, so its absence is the assertion.
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
