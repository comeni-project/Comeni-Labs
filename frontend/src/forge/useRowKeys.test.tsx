import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { useRowKeys } from "./useRowKeys";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

function press(key: string) {
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
}

describe("moving through rows", () => {
  it("starts on the first row", () => {
    const { result } = renderHook(() => useRowKeys(["a", "b", "c"]), { wrapper });
    expect(result.current.index).toBe(0);
  });

  it("J moves down and K moves back", () => {
    const { result } = renderHook(() => useRowKeys(["a", "b", "c"]), { wrapper });
    press("j");
    expect(result.current.index).toBe(1);
    press("k");
    expect(result.current.index).toBe(0);
  });

  it("stops at the ends rather than wrapping", () => {
    // Wrapping in a work queue means pressing J past the last item silently returns you to
    // work you already looked at, and you do not notice for several rows.
    const { result } = renderHook(() => useRowKeys(["a", "b"]), { wrapper });
    press("k");
    expect(result.current.index).toBe(0);
    press("j");
    press("j");
    press("j");
    expect(result.current.index).toBe(1);
  });

  it("does not move when a field has focus", () => {
    const { result } = renderHook(() => useRowKeys(["a", "b"]), { wrapper });
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    act(() => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "j", bubbles: true }));
    });
    expect(result.current.index).toBe(0);
    input.remove();
  });

  it("clamps when the list shrinks under it", () => {
    // Answer the last row and the list gets shorter. An index pointing past the end renders
    // nothing selected and ↵ navigates to `undefined`.
    const { result, rerender } = renderHook(({ rows }) => useRowKeys(rows), {
      wrapper,
      initialProps: { rows: ["a", "b", "c"] },
    });
    press("j");
    press("j");
    expect(result.current.index).toBe(2);
    rerender({ rows: ["a"] });
    expect(result.current.index).toBe(0);
  });
});
