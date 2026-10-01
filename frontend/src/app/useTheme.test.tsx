import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { painted, useTheme } from "./useTheme";

afterEach(() => localStorage.clear());

describe("the theme", () => {
  it("drops the old toggle's key and follows the system", () => {
    // The old shell wrote `comeni-theme` on every mount, including a value it had only worked
    // out from the OS, so a stored value is not evidence of a choice (review I-1).
    localStorage.setItem("comeni-theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("system");
    expect(localStorage.getItem("comeni-theme")).toBeNull();
  });

  it("paints an explicit choice as itself", () => {
    expect(painted("dark")).toBe("dark");
    expect(painted("light")).toBe("light");
  });
});
