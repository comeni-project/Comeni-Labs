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
  it("sends / to the queue, because the landing page is 3B", async () => {
    const router = at("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/forge/queue"));
  });

  it("keeps the shell mounted across navigation", async () => {
    at("/forge/queue");
    // The nav is in the layout route, so it must be present on a child route too — that is
    // what makes the registry panel able to stay open across navigation. Asserted on the
    // landmark, not on the word "Forge": the design uses it twice, as the wordmark and as a
    // workspace tab, and both are right.
    await waitFor(() => expect(screen.getByRole("navigation")).toBeTruthy());
  });

  it("says so where a destination does not exist yet", () => {
    at("/forge/queue");
    // Six dead `href="#"` links are what made slice 1 look finished. A destination that is
    // not built is disabled and titled with the phase that builds it.
    // **One, not two:** `Contracts` became a real link in phase 4 and `Sources` in phase 6.
    // The list shrinks as phases land, and it must shrink deliberately rather than the
    // assertion being deleted — `Mendel` is the last one, and it is 3C.
    for (const name of ["Mendel"]) {
      expect(screen.getByText(name).getAttribute("aria-disabled")).toBe("true");
    }
    expect(document.querySelectorAll('a[href="#"]').length).toBe(0);
  });

  it("puts a question's identity in the path so it can be linked", () => {
    const router = at("/forge/queue/question/consumes%5B0%5D.type_id");
    expect(router.state.location.pathname).toContain("consumes");
  });
});
