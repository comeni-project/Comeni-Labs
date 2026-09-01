import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Cancel } from "./Cancel";

/** **The first control in Wiener that changes anything**, so these are about restraint rather
 *  than about the happy path. */

function at() {
  const calls: [string, RequestInit][] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init: RequestInit) => {
    calls.push([url, init]);
    return Promise.resolve({ ok: true, json: async () => ({ outcome: "signalled", message: "" }) });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Cancel runId="r1" />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("does not stop a run on one click", async () => {
  // **The whole point of the confirm step.** This ends a run somebody may have waited hours
  // for, and every other control on the page only reads. A single-click cancel beside a
  // single-click tab switch is a misclick waiting to happen.
  const calls = at();
  await userEvent.click(screen.getByTestId("cancel-run"));

  expect(screen.getByTestId("cancel-confirm")).toBeInTheDocument();
  expect(calls.filter(([url]) => url.includes("/cancel"))).toEqual([]);
});

it("sends the why with the verb, because the audit row has nowhere else to get it", async () => {
  // §11's audit line is *who · when · why · prior phase · resulting run id*, and `why` is the
  // only one a person supplies. Collected at the confirm step or it is never collected.
  const calls = at();
  await userEvent.click(screen.getByTestId("cancel-run"));
  await userEvent.type(screen.getByLabelText("why"), "wrong reference genome");
  await userEvent.click(screen.getByTestId("cancel-confirm-yes"));

  const sent = calls.find(([url]) => url.includes("/cancel"));
  expect(sent).toBeTruthy();
  expect(JSON.parse(String(sent![1].body))).toEqual({ why: "wrong reference genome" });
});

it("lets somebody back out", async () => {
  const calls = at();
  await userEvent.click(screen.getByTestId("cancel-run"));
  await userEvent.click(screen.getByText("keep it running"));

  expect(screen.getByTestId("cancel-run")).toBeInTheDocument();
  expect(calls.filter(([url]) => url.includes("/cancel"))).toEqual([]);
});

it("shows the refusal's sentence, not its status code", async () => {
  // **Found in the browser.** The server answers *this run is already succeeded* or *this run
  // was launched on another host, cancel it there* — sentences somebody can act on — and the
  // client threw them away for `/api/runs/…/cancel → 409`. A refusal's whole value is its
  // reason; a status code sends a reader to the logs for something already on the wire.
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false,
    status: 409,
    json: async () => ({ detail: "this run is already succeeded; there is nothing to cancel" }),
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Cancel runId="r1" />
    </QueryClientProvider>,
  );

  await userEvent.click(screen.getByTestId("cancel-run"));
  await userEvent.click(screen.getByTestId("cancel-confirm-yes"));
  expect(await screen.findByTestId("cancel-error"))
    .toHaveTextContent("already succeeded");
});
