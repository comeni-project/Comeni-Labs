import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Help } from "./Help";

const HELP = "How the build walks you through its steps.";

describe("the ⓘ", () => {
  it("opens on click and says what the setting is", async () => {
    render(<Help label="Pacing" help={HELP} />);
    expect(screen.queryByText(HELP)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(HELP)).toBeTruthy();
  });

  it("opens on Enter and closes on Escape", async () => {
    render(<Help label="Pacing" help={HELP} />);
    screen.getByRole("button", { name: "About Pacing" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByText(HELP)).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByText(HELP)).toBeNull();
  });

  it("says why when the setting is greyed out", async () => {
    render(<Help label="Pacing" help={HELP} reason="Pinned by .env (COMENI_BUILD_PACING)." />);
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(/Why it is greyed out/)).toBeTruthy();
    expect(screen.getByText(/COMENI_BUILD_PACING/)).toBeTruthy();
  });
});
