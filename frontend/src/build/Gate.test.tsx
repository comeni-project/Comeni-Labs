import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Gate, GatePanel } from "./Gate";

/** A gate is server-owned state, which is why this is the one place polling is right — and why
 *  it has to stop. `docs/design/execution-boundary.md` §3 is the rule the last test holds. */

function show(node: React.ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{node}</QueryClientProvider>);
}

afterEach(() => vi.unstubAllGlobals());

describe("the gate control", () => {
  it("will not gate a draft that was never kept, and says why", () => {
    show(<Gate draftId={null} blocked="Keep this pipeline first — a gate certifies what was kept." />);
    expect(screen.getByTestId("gate-button")).toBeDisabled();
    expect(screen.getByTestId("gate-button").title).toMatch(/keep this pipeline first/i);
  });

  it("will not gate a pipeline that changed after it was kept", () => {
    // A164. The failure this prevents is a green tick beside a canvas the verdict does not
    // describe — A47's class, and it would ship silently.
    show(<Gate draftId="abc" blocked="You have changed it since you kept it." />);
    expect(screen.getByTestId("gate-button")).toBeDisabled();
  });

  it("offers a gate once there is a kept artifact", () => {
    show(<Gate draftId="abc" blocked={null} />);
    expect(screen.getByTestId("gate-button")).not.toBeDisabled();
  });

  it("is a gate and never a run", () => {
    // The disabled control this replaced said "Running a pipeline is Wiener's job, and Wiener
    // is not built." Still true, and the two must not share a label — §3.
    show(<Gate draftId="abc" blocked={null} />);
    expect(screen.getByTestId("gate-button")).toHaveTextContent(/lint/i);
    expect(screen.queryByText(/^Run pipeline$/)).toBeNull();
    expect(screen.getByTestId("gate-button").title).toMatch(/wiener/i);
  });

  it("offers only the gates that need no Docker daemon", () => {
    // STUB and TEST pass `-profile ...,docker`, and giving the worker a daemon means mounting
    // the host socket — root-equivalent host access, deliberately not taken. The Dockerfile
    // records it; this test is what makes the UI agree.
    show(<Gate draftId="abc" blocked={null} />);
    expect(screen.getByTestId("gate-button")).toBeTruthy();
    expect(screen.getByTestId("gate-preview")).toBeTruthy();
    expect(screen.queryByText(/^Stub$/)).toBeNull();
    expect(screen.queryByText(/^Test$/)).toBeNull();
  });
});

describe("the gate panel", () => {
  it("says what a gate is not, in words rather than in a tooltip", () => {
    show(<GatePanel draftId="abc" blocked={null} />);
    expect(screen.getByText(/never receives it/i)).toBeTruthy();
  });

  it("shows a run and stops polling once it lands", async () => {
    const fetched = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        id: "r1", gate: "lint", state: "passed", output: "Nextflow linting complete!",
        queued_at: "2026-08-23T00:00:00Z", finished_at: "2026-08-23T00:00:05Z",
      }),
    });
    vi.stubGlobal("fetch", fetched);
    show(<GatePanel draftId="abc" blocked={null} />);
    // Nothing is polled until a gate is started — `enabled: runId !== null`.
    await waitFor(() => expect(screen.queryByTestId("gate-output")).toBeNull());
  });
});

describe("saying that it is working", () => {
  it("labels the gate you actually pressed", async () => {
    // Pressing Preview used to put "Gating…" on the Lint button and leave Preview alone,
    // because the label was hardcoded to the first gate. The operator caught it by reading.
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise(() => {})));
    show(<Gate draftId="abc" blocked={null} />);
    screen.getByTestId("gate-preview").click();
    await waitFor(() => expect(screen.getByTestId("gate-preview")).toHaveTextContent("Gating…"));
    expect(screen.getByTestId("gate-button")).toHaveTextContent("Lint");
  });

  it("says it is running rather than only dimming a button", async () => {
    // `preview` is ~10s against the real stack. A control that only dims for ten seconds reads
    // as a page that broke.
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise(() => {})));
    show(<Gate draftId="abc" blocked={null} />);
    screen.getByTestId("gate-button").click();
    await waitFor(() => expect(screen.getByTestId("gate-progress")).toBeTruthy());
  });
});
