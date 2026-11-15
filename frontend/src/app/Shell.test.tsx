import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DOCS_URL } from "./address";
import { routes } from "./router";

/** The frame every page sits in: the one rail beside the page (#511). */
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

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })));
});
afterEach(() => vi.unstubAllGlobals());

describe("the shell", () => {
  it("draws the rail beside the page", () => {
    at("/registry");
    const rail = screen.getByRole("navigation", { name: "Comeni" });
    expect(within(rail).getByRole("link", { name: "Registry" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("main")).toBeTruthy();
  });

  it("opens the docs from help, in a new tab", () => {
    at("/registry");
    const help = screen.getByRole("link", { name: "Help" });
    expect(help.getAttribute("href")).toBe(DOCS_URL);
    expect(help.getAttribute("target")).toBe("_blank");
    expect(help.getAttribute("rel")).toContain("noreferrer");
  });

  it("gives help and settings a 44 px target at phone width (issue 383)", () => {
    at("/registry");
    for (const name of ["Help", "Settings"]) {
      const classes = screen.getByRole("link", { name }).className.split(/\s+/);
      expect(classes).toEqual(expect.arrayContaining(["w-11", "h-11", "sm:w-9", "sm:h-9"]));
    }
  });

  it("keeps settings one click away, over the page you are on", () => {
    at("/registry/releases");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("href")).toBe("/registry/releases?settings=");
  });

  it("sends the old addresses to their analysis", () => {
    expect(at("/build?draft=d1").state.location.pathname).toBe("/a/d1/build");
  });

  it("names no lab and offers nothing that does not exist yet", () => {
    at("/registry");
    expect(screen.queryByText(/Learn in Code/)).toBeNull();
    expect(screen.queryByText(/\blab$/i)).toBeNull();
  });
});
