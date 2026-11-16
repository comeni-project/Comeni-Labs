import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { FolderTree } from "./FolderTree";

const listing = (path: string | null) => path === null
  ? { path: null, files: 0, folders: [{ name: "data", path: "/data", files: 0 }] }
  : { path, files: 0, folders: [{ name: "liver", path: "/data/liver", files: 48 }] };

vi.mock("../../api/client", () => ({
  get: vi.fn(async (url: string) => listing(url.includes("path=") ? decodeURIComponent(url.split("path=")[1]) : null)),
}));

afterEach(() => vi.clearAllMocks());

function tree(ticked: string[], onTick = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FolderTree ticked={ticked} onTick={onTick} />
    </QueryClientProvider>,
  );
  return onTick;
}

it("ticking a folder sends the folder list with it added", async () => {
  const onTick = tree([]);
  fireEvent.click(await screen.findByRole("button", { name: "Open data" }));
  fireEvent.click(await screen.findByRole("button", { name: /^liver,/ }));
  expect(onTick).toHaveBeenCalledWith(["/data/liver"]);
});

it("unticking a ticked folder sends the list without it", async () => {
  const onTick = tree(["/data/liver"]);
  const liver = await screen.findByRole("button", { name: /^liver,/ });
  expect(liver.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(liver);
  expect(onTick).toHaveBeenCalledWith([]);
});

it("cloud storage is shown and disabled", async () => {
  tree([]);
  const cloud = await screen.findByText("Cloud storage");
  expect(cloud.closest("[aria-disabled='true']")).not.toBeNull();
  expect(screen.getByText("later")).toBeTruthy();
});

it("opens down to a ticked folder, so it is in sight", async () => {
  tree(["/data/liver"]);
  expect((await screen.findByRole("button", { name: /^liver,/ })).getAttribute("aria-pressed")).toBe("true");
});
