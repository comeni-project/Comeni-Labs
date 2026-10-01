import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Report } from "./Report";

describe("a report", () => {
  it("draws a list of records as a table", () => {
    render(<Report value={[{ purpose: "Talking with you", goes: "stays on this machine or your network" }]} />);
    expect(screen.getByRole("columnheader", { name: "purpose" })).toBeTruthy();
    expect(screen.getByRole("cell", { name: "Talking with you" })).toBeTruthy();
  });

  it("draws anything else as text", () => {
    render(<Report value="0.1.0" />);
    expect(screen.getByText("0.1.0")).toBeTruthy();
  });
});
