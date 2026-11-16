import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";

import { Assistant } from "./Assistant";

const configured = { value: true };
vi.mock("../home/useAiConfigured", () => ({
  useAiConfigured: () => ({ pending: false, configured: configured.value }),
}));
vi.mock("../api/client", () => ({
  post: vi.fn(async () => ({ session_id: "s1" })),
}));
vi.mock("../build/living/useAuthoringSession", () => ({
  useAuthoringSession: () => ({ session: { id: "s1", turns: [], decision_revision: 0 }, sending: [], composer: "",
                                compose: vi.fn(), say: vi.fn(), answer: vi.fn(), retry: vi.fn(), notice: null }),
}));
vi.mock("../build/living/ChatPanel", () => ({
  ChatPanel: () => <textarea aria-label="Message" />,
}));

beforeEach(() => { configured.value = true; });

function Page() {
  const [n, setN] = useState(0);
  return (
    <>
      <button type="button" onClick={() => setN(n + 1)}>count {n}</button>
      <Assistant draftId="d1" />
    </>
  );
}

function page() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/a/d1/data"]}><Page /></MemoryRouter>
    </QueryClientProvider>,
  );
}

it("drawer opens over the page and keeps page state", async () => {
  page();
  fireEvent.click(screen.getByRole("button", { name: "count 0" }));
  fireEvent.click(screen.getByRole("button", { name: "Assistant" }));
  expect(await screen.findByRole("dialog", { name: "Assistant" })).toBeTruthy();
  expect(await screen.findByRole("textbox", { name: "Message" })).toBeTruthy();
  expect(screen.getByText(/Changes it makes are marked AI/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Close the assistant" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("button", { name: "count 1" })).toBeTruthy();
});

it("without a model the drawer says so and links to settings", () => {
  configured.value = false;
  page();
  fireEvent.click(screen.getByRole("button", { name: "Assistant" }));
  expect(screen.getByText("Needs a model")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Connect a model/ }).getAttribute("href")).toContain("settings=models");
  expect(screen.queryByRole("textbox", { name: "Message" })).toBeNull();
});
