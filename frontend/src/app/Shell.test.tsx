import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { routes } from "./router";
import { DOCS_URL } from "./Shell";

/** The bar every page sits in (redesign part 2, #372). */
function at(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })));
});
afterEach(() => vi.unstubAllGlobals());

describe("the shell's bar", () => {
  it("goes home from the mark and the product's name", () => {
    at("/build");
    const home = screen.getByLabelText("Comeni — home");
    expect(home.getAttribute("href")).toBe("/");
    expect(home.textContent).toContain("Comeni Labs");
    expect(home.querySelector("svg")).not.toBeNull();
  });

  it("names the sections, and marks the one you are in", () => {
    // Forge MVP part 1 (#362) brings the Registry back.
    at("/build");
    const bar = screen.getByRole("navigation", { name: "Main" });
    const links = within(bar).getAllByRole("link").filter((a) => a.getAttribute("href")?.match(/^\/(build|runs|registry)$/));
    expect(links.map((a) => a.textContent)).toEqual(["Build", "Runs", "Registry"]);
    expect(links[0].getAttribute("aria-current")).toBe("page");
    expect(links[1].getAttribute("aria-current")).toBeNull();
  });

  it("opens the docs from help, in a new tab", () => {
    at("/build");
    const help = screen.getByRole("link", { name: "Help" });
    expect(help.getAttribute("href")).toBe(DOCS_URL);
    expect(help.getAttribute("target")).toBe("_blank");
    expect(help.getAttribute("rel")).toContain("noreferrer");
  });

  it("keeps settings one click away", () => {
    at("/build");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("href")).toContain("settings=");
  });

  it("names no lab and offers nothing that does not exist yet", () => {
    at("/build");
    expect(screen.queryByText(/Learn in Code/)).toBeNull();
    expect(screen.queryByText(/\blab$/i)).toBeNull();
  });
});
