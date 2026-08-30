import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { Walk } from "./Walk";

const DRAWN = { steps: 4, problems: 0 };

it("derives each step from state and never from an index", () => {
  render(
    <Walk draw={DRAWN} keep={{ keptAt: "3 minutes ago", error: null }} gate={{ passed: true, error: null }}
          run={{ sent: false, error: null }} />,
  );
  expect(screen.getByTestId("step-gate")).toHaveAttribute("data-state", "done");
  expect(screen.getByTestId("step-run")).toHaveAttribute("data-state", "now");
});

it("puts the blocked reason on the screen rather than in a title", () => {
  // A disabled control with a hidden reason is a dead end. The reason is the only thing that
  // makes it a step rather than a wall.
  render(
    <Walk draw={DRAWN}
          keep={{ keptAt: "3 minutes ago", error: null,
                  stale: "You have changed it since you kept it. Keep again to gate the new version." }}
          gate={{ passed: false, blocked: "A gate has to pass on the version you kept.",
                  error: null }}
          run={{ sent: false, error: null }} />,
  );
  expect(screen.getByTestId("step-keep")).toHaveTextContent("changed it since you kept it");
  expect(screen.getByTestId("step-gate")).toHaveTextContent("has to pass on the version you kept");
});

it("goes backwards when the graph changes after it was kept", () => {
  // The whole reason each step reads the world rather than a counter: editing after keeping
  // un-keeps you, and a rail that only advances would say you were still ready to gate.
  render(
    <Walk draw={DRAWN} keep={{ keptAt: "3 minutes ago", stale: "You have changed it.", error: null }}
          gate={{ passed: false, error: null }} run={{ sent: false, error: null }} />,
  );
  expect(screen.getByTestId("step-keep")).toHaveAttribute("data-state", "now");
  expect(screen.getByTestId("step-gate")).toHaveAttribute("data-state", "waiting");
});

it("says nothing is drawn rather than starting at step two", () => {
  render(<Walk draw={{ steps: 0, problems: 0 }} keep={{ error: null }} gate={{ passed: false, error: null }}
               run={{ sent: false, error: null }} />);
  expect(screen.getByTestId("step-draw")).toHaveAttribute("data-state", "now");
  expect(screen.getByTestId("step-keep")).toHaveAttribute("data-state", "waiting");
});

it("says so when a step's mutation failed, rather than sitting there unchanged", () => {
  // **The defect this whole phase exists for.** On 2026-08-29 a hand-drawn pipeline was walked
  // end to end and *Keep* answered 500: the rail did not change, still offered *Keep*, printed
  // nothing on screen and nothing to the console, and `docker logs` was the only way to learn
  // that the page's central action had failed. Every other item on that walk's list is
  // friction; this one is a lie by omission.
  //
  // Note the state: the step is `now`, not `done` — a failed mutation does not advance the
  // walk, so an error rendered only on a finished step would be an error nobody ever sees.
  render(
    <Walk draw={DRAWN}
          keep={{ error: "MD0512: a step consumes a type nothing in this graph produces" }}
          gate={{ passed: false, error: null }} run={{ sent: false, error: null }} />,
  );
  const step = screen.getByTestId("step-keep");
  expect(step).toHaveAttribute("data-state", "now");
  expect(step).toHaveTextContent("a type nothing in this graph produces");
});

it("keeps a coded refusal lookup-able wherever it surfaces", () => {
  // `Failed` defers to `Refusal` on a code, so `MD0512` keeps its `explain` line here as well
  // as on the screens that were already rendering refusals. One renderer, one behaviour.
  render(
    <Walk draw={DRAWN} keep={{ error: "MD0512: a step consumes a type nothing produces" }}
          gate={{ passed: false, error: null }} run={{ sent: false, error: null }} />,
  );
  expect(screen.getByTestId("step-keep")).toHaveTextContent("explain MD0512");
});
