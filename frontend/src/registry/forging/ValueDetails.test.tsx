import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ValueDetails } from "./ValueDetails";

describe("ValueDetails", () => {
  it("shows a measurer's parser code and tests as code (#487)", () => {
    const code = "def parse(stream, decided):\n    return None\n";
    render(<ValueDetails value={{ measures: "genome_length", output: "fai", code, tests: "def test_x():\n    pass\n" }} />);
    const shown = screen.getByText((_, el) => el?.tagName === "PRE" && el.textContent === code);
    expect(shown.className).toContain("font-mono");
    expect(screen.getByText("Parser tests")).toBeTruthy();
    expect(screen.getByText("Reads output")).toBeTruthy();
  });
});
