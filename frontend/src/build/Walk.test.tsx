import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { Walk } from "./Walk";

const DRAWN = { steps: 4, problems: 0 };

it("derives each step from state and never from an index", () => {
  render(
    <Walk draw={DRAWN} keep={{ keptAt: "3 minutes ago" }} gate={{ passed: true }}
          run={{ sent: false }} />,
  );
  expect(screen.getByTestId("step-gate")).toHaveAttribute("data-state", "done");
  expect(screen.getByTestId("step-run")).toHaveAttribute("data-state", "now");
});

it("puts the blocked reason on the screen rather than in a title", () => {
  // A disabled control with a hidden reason is a dead end. The reason is the only thing that
  // makes it a step rather than a wall.
  render(
    <Walk draw={DRAWN}
          keep={{ keptAt: "3 minutes ago",
                  stale: "You have changed it since you kept it. Keep again to gate the new version." }}
          gate={{ passed: false, blocked: "A gate has to pass on the version you kept." }}
          run={{ sent: false }} />,
  );
  expect(screen.getByTestId("step-keep")).toHaveTextContent("changed it since you kept it");
  expect(screen.getByTestId("step-gate")).toHaveTextContent("has to pass on the version you kept");
});

it("goes backwards when the graph changes after it was kept", () => {
  // The whole reason each step reads the world rather than a counter: editing after keeping
  // un-keeps you, and a rail that only advances would say you were still ready to gate.
  render(
    <Walk draw={DRAWN} keep={{ keptAt: "3 minutes ago", stale: "You have changed it." }}
          gate={{ passed: false }} run={{ sent: false }} />,
  );
  expect(screen.getByTestId("step-keep")).toHaveAttribute("data-state", "now");
  expect(screen.getByTestId("step-gate")).toHaveAttribute("data-state", "waiting");
});

it("says nothing is drawn rather than starting at step two", () => {
  render(<Walk draw={{ steps: 0, problems: 0 }} keep={{}} gate={{ passed: false }}
               run={{ sent: false }} />);
  expect(screen.getByTestId("step-draw")).toHaveAttribute("data-state", "now");
  expect(screen.getByTestId("step-keep")).toHaveAttribute("data-state", "waiting");
});
