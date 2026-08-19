import { act, renderHook } from "@testing-library/react";
import { MemoryRouter, useSearchParams } from "react-router";
import { describe, expect, it } from "vitest";

import { useUrlState } from "./useUrlState";

function at(search: string) {
  return ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter initialEntries={[`/forge/queue${search}`]}>{children}</MemoryRouter>
  );
}

describe("useUrlState", () => {
  it("reads the parameter out of the URL", () => {
    const { result } = renderHook(() => useUrlState("sort", "consequence"), {
      wrapper: at("?sort=recent"),
    });
    expect(result.current[0]).toBe("recent");
  });

  it("falls back when the parameter is absent", () => {
    const { result } = renderHook(() => useUrlState("sort", "consequence"), { wrapper: at("") });
    expect(result.current[0]).toBe("consequence");
  });

  it("drops the parameter rather than writing the default into the URL", () => {
    // `?sort=consequence&band=&group=question` is noise in a link somebody has to read.
    // A URL should say what is UNUSUAL about the view.
    //
    // **Asserted through `useSearchParams`, never `window.location`.** MemoryRouter keeps its
    // history in memory and never touches the address bar, so `window.location.search` is ""
    // for the whole test — `expect("").not.toContain("sort")` passes even if `set` does
    // nothing at all. That version was written, run, and passed; this one can fail.
    const { result } = renderHook(
      () => {
        const [params] = useSearchParams();
        return { state: useUrlState("sort", "consequence"), search: params.toString() };
      },
      { wrapper: at("?sort=recent") },
    );
    expect(result.current.search).toContain("sort");
    act(() => result.current.state[1]("consequence"));
    expect(result.current.search).not.toContain("sort");
  });
});
