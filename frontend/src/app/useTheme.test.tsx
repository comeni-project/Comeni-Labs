import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { painted, useTheme } from "./useTheme";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

/** A system that reports `dark`, or no preference at all. */
function systemPrefers(dark: boolean) {
  vi.spyOn(window, "matchMedia").mockImplementation((query: string) => ({
    matches: dark && query === "(prefers-color-scheme: dark)",
    media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }));
}

describe("the theme", () => {
  it("follows the system until someone chooses", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("system");
  });

  it("paints light when the system asks for nothing", () => {
    systemPrefers(false);
    expect(painted("system")).toBe("light");
  });

  it("paints dark when the system asks for dark", () => {
    systemPrefers(true);
    expect(painted("system")).toBe("dark");
  });

  it("paints an explicit choice as itself, whatever the system says", () => {
    systemPrefers(true);
    expect(painted("light")).toBe("light");
    expect(painted("dark")).toBe("dark");
  });
});
