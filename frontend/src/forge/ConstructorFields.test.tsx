import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";

import { Fields, type Schema } from "./ConstructorFields";

it("removing an entry retains the surviving value's kind and editable value", () => {
  const schema: Schema = { type: "array", items: {} };
  function Form() {
    const [value, setValue] = useState<unknown>(["first", 42]);
    return <Fields schema={schema} root={schema} value={value} onChange={setValue} label="Values" />;
  }
  render(<Form />);
  fireEvent.change(screen.getByLabelText("Values 1 kind"), { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "Remove values 1" }));
  expect(screen.getByLabelText("Values 1 kind")).toHaveValue("1");
  expect(screen.getByRole("spinbutton", { name: "Values 1" })).toHaveValue(42);
  fireEvent.change(screen.getByRole("spinbutton", { name: "Values 1" }), { target: { value: "43" } });
  expect(screen.getByRole("spinbutton", { name: "Values 1" })).toHaveValue(43);
});
