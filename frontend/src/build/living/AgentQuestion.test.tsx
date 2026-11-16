import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { expect, it, vi } from "vitest";

import type { AuthoringBlock } from "../../api/types";
import { AgentQuestion } from "./AgentQuestion";

type Ask = Extract<AuthoringBlock, { kind: "ask" }>;

it("a data question sends the person to the analysis's Data page, and takes no file", () => {
  const question = { kind: "ask", id: "b1", question_id: "q1", question: "Which reads are yours?",
    shape: "data", options: [], unit: "", type_id: "reads.fastq" } as unknown as Ask;
  render(
    <MemoryRouter initialEntries={["/a/d1/build"]}>
      <Routes>
        <Route path="/a/:draft/build" element={<AgentQuestion question={question} onAnswer={vi.fn()} />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Open Data" }).getAttribute("href")).toBe("/a/d1/data");
  expect(document.querySelector("input[type=file]")).toBeNull();
});
