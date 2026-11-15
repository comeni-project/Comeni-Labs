import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnalysisSlot } from "./AnalysisSlot";
import { Rail } from "./Rail";
import { RailControls, RailProvider, RailSlot } from "./RailContext";

vi.mock("../../api/client", () => ({
  get: vi.fn(async (path: string) =>
    path.startsWith("/pipeline/drafts/")
      ? { id: "d1", name: "Liver RNA-seq counts" }
      : { drafts: [{ id: "d1", name: "Liver RNA-seq counts" }] }),
}));

function at(path: string, page: ReactNode = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <RailProvider>
          <Rail />
          {page}
        </RailProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const rail = () => screen.getByRole("navigation", { name: "Comeni" });

afterEach(() => localStorage.clear());

describe("the rail", () => {
  it("places are always Home, Forge, Registry", () => {
    at("/");
    const places = within(rail()).getByRole("list", { name: "Places" });
    expect(within(places).getAllByRole("link").map((a) => a.textContent)).toEqual(["Home", "Forge", "Registry"]);
  });

  it('the slot shows "Open an analysis…" when no analysis is open', () => {
    at("/");
    expect(within(rail()).getByText("Open an analysis…")).toBeTruthy();
  });

  it("inside an analysis the active page's sub-pages are indented under it", async () => {
    at("/a/d1/data/samples", <RailSlot><AnalysisSlot draftId="d1" page="data" /></RailSlot>);
    expect(within(rail()).queryByText("Open an analysis…")).toBeNull();
    const data = within(rail()).getByRole("list", { name: "Data pages" });
    expect(within(data).getAllByRole("link").map((a) => a.textContent)).toEqual(
      ["Overview", "Samples", "References", "Files"]);
    expect(within(data).getByRole("link", { name: "Samples" }).getAttribute("aria-current")).toBe("page");
    expect(within(rail()).getByRole("link", { name: /Build/ })).toBeTruthy();
    expect(within(rail()).getByRole("link", { name: /Run/ })).toBeTruthy();
    expect(await within(rail()).findByText("Liver RNA-seq counts")).toBeTruthy();
  });

  it("controls render under a divider with their label", () => {
    at("/", <RailControls label="Folders"><p>tree</p></RailControls>);
    const group = within(rail()).getByRole("group", { name: "Folders" });
    expect(within(group).getByText("tree")).toBeTruthy();
    expect(group.previousElementSibling?.getAttribute("role")).toBe("separator");
  });

  it("the bottom row is Settings, theme, Local", () => {
    at("/");
    const foot = within(rail()).getByRole("group", { name: "This machine" });
    expect(within(foot).getByRole("link", { name: "Settings" }).getAttribute("href")).toContain("settings=");
    expect(within(foot).getByRole("button", { name: /theme/i })).toBeTruthy();
    expect(within(foot).getByText("Local")).toBeTruthy();
  });

  it("collapsed rail hides labels and sub-pages", () => {
    at("/a/d1/data", <RailSlot><AnalysisSlot draftId="d1" page="data" /></RailSlot>);
    fireEvent.click(within(rail()).getByRole("button", { name: "Collapse sidebar" }));
    expect(within(rail()).queryByRole("list", { name: "Data pages" })).toBeNull();
    expect(within(rail()).getByRole("link", { name: "Home" }).textContent).toBe("");
    expect(within(rail()).getByRole("button", { name: "Expand sidebar" })).toBeTruthy();
  });

  it("on a phone starts as icons, and opens over the page", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("max-width"), addEventListener: () => {}, removeEventListener: () => {},
    }));
    at("/a/d1/data", <RailSlot><AnalysisSlot draftId="d1" page="data" /></RailSlot>);
    expect(within(rail()).queryByRole("list", { name: "Data pages" })).toBeNull();
    fireEvent.click(within(rail()).getByRole("button", { name: "Expand sidebar" }));
    expect(within(rail()).getByRole("list", { name: "Data pages" })).toBeTruthy();
    expect(rail().className).toContain("fixed");
    vi.unstubAllGlobals();
  });
});
