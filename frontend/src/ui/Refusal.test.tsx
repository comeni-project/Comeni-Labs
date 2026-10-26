import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Refusal } from "./Refusal";

describe("Refusal", () => {
  it("shows the code, because the code is what you can look up", () => {
    // `mendel explain MI0106` expands it. Replacing the code with friendlier copy would hide
    // the one string that tells a user what to do.
    render(<Refusal message="MI0106: no model is configured, so nothing can be generated" />);
    // Twice on purpose: once in the message the API sent, once as the command that expands
    // it. `getByText` would fail on that, and dropping either one is the regression.
    expect(screen.getByText(/nothing can be generated/)).toBeTruthy();
    expect(screen.getByText(/mendel explain MI0106/)).toBeTruthy();
  });

  it("renders an uncoded message unchanged rather than inventing a code", () => {
    render(<Refusal message="an answer needs a reason" />);
    expect(screen.getByText(/needs a reason/)).toBeTruthy();
  });
});
