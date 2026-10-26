import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

/** The composer as the *Build* board draws it: a field and a Send button beside it. */

describe("the composer", () => {
  it("sends what is typed with the Send button, trimmed", () => {
    const onSend = vi.fn();
    render(<Composer value="  why STAR?  " onChange={vi.fn()} onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("why STAR?");
  });

  it("cannot send nothing", () => {
    render(<Composer value="   " onChange={vi.fn()} onSend={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("cannot send while the composer is disabled", () => {
    render(<Composer value="why?" onChange={vi.fn()} onSend={vi.fn()} disabled />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});
