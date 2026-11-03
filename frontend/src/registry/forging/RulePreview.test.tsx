import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { RulePreview } from "./RulePreview";
import type { ItemView } from "./useAdaptation";

const item = { key: "rules:rule:alignment", current_n: 4, value: {
  rows: [{ when: { read_length: ">= 70" }, then: "browser must not choose this" }],
} } as unknown as ItemView;

afterEach(() => vi.unstubAllGlobals());

it("the slider sends hypothetical facts and renders the server's decision", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ revision: 4, effects: [
    { effect: "implementation", role: "alignment", value: "server choice", because: "Server evidence", cite: "Paper" },
  ] }) });
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={makeClient()}><RulePreview id="a1" item={item} /></QueryClientProvider>);
  expect(await screen.findByText("server choice")).toBeTruthy();
  expect(screen.queryByText("browser must not choose this")).toBeNull();
  fireEvent.change(screen.getByRole("slider"), { target: { value: "69" } });
  await vi.waitFor(() => expect(fetch.mock.calls.some(([url, init]) => String(url).endsWith("/rule-preview")
    && JSON.parse(init.body).expected === 4 && JSON.parse(init.body).premises.read_length === 69)).toBe(true));
  expect(fetch.mock.calls.every(([url]) => !String(url).includes("/commands"))).toBe(true);
});

it("a miss remains unresolved and a stale revision displays the refusal", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ effects: [] }) })
    .mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "MF0506: the rule changed since you looked" }) }));
  render(<QueryClientProvider client={makeClient()}><RulePreview id="a1" item={item} /></QueryClientProvider>);
  expect(await screen.findByText(/remains unresolved/)).toBeTruthy();
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "70" } });
  expect(await screen.findByText(/rule changed since you looked/)).toBeTruthy();
  expect(screen.queryByText("server choice")).toBeNull();
});

it("a hypothetical fact can be given a numeric kind even when its condition is membership", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ effects: [] }) });
  vi.stubGlobal("fetch", fetch);
  const membership = { ...item, value: { rows: [{ when: { sample_count: { in: [1, 2] } }, then: true }] } };
  render(<QueryClientProvider client={makeClient()}><RulePreview id="a1" item={membership} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("sample_count kind"), { target: { value: "number" } });
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "2" } });
  await vi.waitFor(() => expect(fetch.mock.calls.some(([, init]) =>
    JSON.parse(init.body).premises.sample_count === 2)).toBe(true));
});
