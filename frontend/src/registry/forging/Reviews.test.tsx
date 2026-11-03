import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { useReviews } from "./Reviews";

afterEach(() => vi.unstubAllGlobals());

it("refreshes comments when the reviewer finishes even if the earlier idle query was cached", async () => {
  let comments: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => ({
    ok: true, status: 200, json: async () => comments,
  })));
  const client = makeClient();
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { result, rerender } = renderHook(({ working }) => useReviews("a1", working, "item:1"), {
    initialProps: { working: false }, wrapper,
  });
  await waitFor(() => expect(result.current.data).toEqual([]));
  rerender({ working: true });
  await waitFor(() => expect(result.current.isFetching).toBe(false));
  comments = [{ item: "questions:role", revision: 1, comment: "Check the role.", quote: null, file: null, model: "fixture" }];
  rerender({ working: false });
  await waitFor(() => expect(result.current.data).toEqual(comments));
});
