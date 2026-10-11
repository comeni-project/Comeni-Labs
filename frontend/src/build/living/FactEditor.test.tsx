import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { FactEditor } from "./FactEditor";

it("corrects a declared number by keyboard and explicitly retracts to unknown", async () => {
  const save = vi.fn().mockResolvedValue(undefined);
  render(<FactEditor subject="read_length" value={150} kind="measurement"
    declaration={{ id: "read_length", kind: "integer", minimum: 1 }} onSave={save} />);
  const user = userEvent.setup();
  await user.clear(screen.getByLabelText("read_length"));
  await user.type(screen.getByLabelText("read_length"), "50");
  await user.click(screen.getByRole("button", { name: "Save correction" }));
  expect(save).toHaveBeenCalledWith(50);
  await user.click(screen.getByRole("button", { name: "Return to unknown" }));
  expect(save).toHaveBeenCalledWith(null);
});

it("keeps the person's typed correction after a revision refusal", async () => {
  const save = vi.fn().mockRejectedValue(new Error("MI0201: reload before correcting"));
  render(<FactEditor subject="paired" value={true} kind="measurement"
    declaration={{ id: "paired", kind: "boolean" }} onSave={save} />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("paired"), "false");
  await user.click(screen.getByRole("button", { name: "Save correction" }));
  expect(screen.getByRole("alert")).toHaveTextContent("reload");
  expect(screen.getByLabelText("paired")).toHaveValue("false");
});
