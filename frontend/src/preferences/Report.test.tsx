import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Report } from "./Report";

describe("a report", () => {
  it("draws a list of records as a stacked list, the first field as each line", () => {
    render(<Report value={[{ purpose: "Talking with you", goes: "stays on this machine", connection: "Local" }]} />);
    expect(screen.getByRole("listitem")).toBeTruthy();
    expect(screen.getByText("Talking with you")).toBeTruthy();
    expect(screen.getByText("stays on this machine · Local")).toBeTruthy();
  });

  it("draws a list of values on one line", () => {
    render(<Report value={["/app/registry", "/app/lab"]} />);
    expect(screen.getByText("/app/registry · /app/lab")).toBeTruthy();
  });

  it("draws anything else as text", () => {
    render(<Report value="0.1.0" />);
    expect(screen.getByText("0.1.0")).toBeTruthy();
  });
});
