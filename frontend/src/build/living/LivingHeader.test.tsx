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
