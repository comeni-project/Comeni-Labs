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
    at("/runs");
    // The shell is in the layout route, so it must be present on a child route too. Asserted
    // on the wordmark, which belongs to the shell and to nothing else.
    await waitFor(() => expect(screen.getByLabelText("Comeni — home")).toBeTruthy());
  });

  it("has no destination left to disable", () => {
    at("/runs");
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

  it("offers no way into the old forge", async () => {
    // The old forge's screens went with it (#361); forge MVP part 1 (#362) builds the new
    // Registry and puts its link back.
    at("/build");
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
    const into = Array.from(screen.getByRole("navigation").querySelectorAll("a"))
      .map((a) => a.getAttribute("href") ?? "")
      .filter((href) => href.startsWith("/forge"));
    expect(into).toEqual([]);
  });

  it.each([["/forge"], ["/forge/catalogue"], ["/forge/queue/question/consumes%5B0%5D.type_id"]])(
    "answers %s as an unknown page",
    async (path) => {
      // No redirects are kept: before v0.1.0 there are no bookmarks to preserve.
      at(path);
      expect(await screen.findByText("Something broke")).toBeTruthy();
      expect(screen.getByText(/404/)).toBeTruthy();
    },
  );
});
