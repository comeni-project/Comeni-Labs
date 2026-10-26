import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FAKE_SESSION } from "./fake";
import { LivingHeader } from "./LivingHeader";

function header(openValues: number) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingHeader session={FAKE_SESSION} view="canvas" onView={vi.fn()} onRun={vi.fn()} running={false}
                    openValues={openValues} />
    </QueryClientProvider>,
  );
}

describe("the builder's header", () => {
  it("names the two views Canvas and Pipeline file", () => {
    header(0);
    expect(screen.getByTestId("living-view-canvas")).toHaveTextContent(/^Canvas$/);
    expect(screen.getByTestId("living-view-artifact")).toHaveTextContent(/^Pipeline file$/);
  });

  it("says how many values need the person, and nothing when none do", () => {
    header(0);
    expect(screen.queryByTestId("needs-you-chip")).toBeNull();
  });

  it.each([[1, "1 value needs you"], [2, "2 values need you"]])("with %i open says %s", (n, words) => {
    header(n);
    expect(screen.getByTestId("needs-you-chip")).toHaveTextContent(words);
  });
});

describe("the header as the boards draw it", () => {
  const draw = (session: typeof FAKE_SESSION, runnable = false, openValues = 0) => render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingHeader session={session} view="canvas" onView={vi.fn()} onRun={vi.fn()} running={false}
                    runnable={runnable} openValues={openValues} />
    </QueryClientProvider>,
  );

  it("says where the build is as a chip, with the step being offered", () => {
    draw(FAKE_SESSION);
    const chip = screen.getByTestId("living-status");
    expect(chip).toHaveTextContent(/^building · step 4 of 5$/);
    expect(chip.getAttribute("data-tone")).toBe("now");
  });

  it("says complete in the done colour, and never claims the pipeline is valid", () => {
    draw({ ...FAKE_SESSION, phase: "complete", pending_proposal: null,
           progress: { reviewed: 5, total: 5, active: null } } as typeof FAKE_SESSION);
    const chip = screen.getByTestId("living-status");
    expect(chip).toHaveTextContent(/^complete$/);
    expect(chip.getAttribute("data-tone")).toBe("done");
    expect(screen.queryByText(/valid/i)).toBeNull();
  });

  it("says a stop in the needs-you colour", () => {
    draw({ ...FAKE_SESSION, phase: "stopped", pending_proposal: null } as typeof FAKE_SESSION);
    expect(screen.getByTestId("living-status").getAttribute("data-tone")).toBe("needs-you");
  });

  it("draws an unavailable Run as the quiet button, not a faded main one", () => {
    draw(FAKE_SESSION, false);
    expect(screen.getByTestId("living-run").className).not.toMatch(/bg-action/);
  });

  it("says no revision number", () => {
    draw(FAKE_SESSION);
    expect(screen.getByTestId("living-header")).not.toHaveTextContent(/revision/);
  });

  const complete = { ...FAKE_SESSION, phase: "complete", pending_proposal: null,
                     progress: { reviewed: 5, total: 5, active: null } } as typeof FAKE_SESSION;

  it("keeps Run locked while a value needs the person, even when every step is added (issue 385)", () => {
    draw(complete, true, 1);
    expect(screen.getByTestId("living-run")).toBeDisabled();
  });

  it("offers Run once nothing needs the person", () => {
    draw(complete, true, 0);
    expect(screen.getByTestId("living-run")).toBeEnabled();
  });

  it("does not say complete while a value needs the person (issue 385)", () => {
    draw(complete, true, 1);
    const chip = screen.getByTestId("living-status");
    expect(chip).toHaveTextContent(/^built$/);
    expect(chip.getAttribute("data-tone")).toBe("now");
  });
});
