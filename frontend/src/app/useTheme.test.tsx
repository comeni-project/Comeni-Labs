import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { painted, useTheme } from "./useTheme";

afterEach(() => localStorage.clear());

describe("the theme", () => {
  it("keeps a choice made with the old toggle", () => {
    localStorage.setItem("comeni-theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
  });

  it("paints an explicit choice as itself", () => {
    expect(painted("dark")).toBe("dark");
    expect(painted("light")).toBe("light");
  });
});
