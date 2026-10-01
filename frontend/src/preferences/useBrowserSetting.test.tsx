import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { storageName, useBrowserSetting } from "./useBrowserSetting";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("a per-browser setting", () => {
  it("starts at the fallback and keeps what is set", () => {
    const { result } = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    expect(result.current[0]).toBe("system");
    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");
    expect(localStorage.getItem(storageName("appearance.theme"))).toBe("dark");
  });

  it("is shared: a second component sees the change at once", () => {
    const a = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    const b = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    act(() => a.result.current[1]("light"));
    expect(b.result.current[0]).toBe("light");
  });

  it("survives a browser that refuses storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    const { result } = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    expect(result.current[0]).toBe("system");
    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");
  });
});
