import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { get } from "../../api/client";
import { CallPanel } from "./CallPanel";
import { purposeWords, usageWords } from "./format";

vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  get: vi.fn(),
}));

const CALL = {
  id: "c1", purpose: "goal", model: "ollama_chat/gemma3:12b", input: 3000, output: 40,
  cached: null, duration_ms: 17000, state: "succeeded", response: '{"want": ["counts.matrix"]}',
  at: "2026-09-29T10:00:00Z",
};

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

describe("the session's token count (issue 191)", () => {
  it("says tokens and calls, and thinking while one is on its way", () => {
    const usage = { input: 12400, output: 900, cached: 0, calls: 7, in_flight: false };
    expect(usageWords(usage)).toBe("13.3k tokens · 7 calls");
    expect(usageWords({ ...usage, in_flight: true })).toBe("13.3k tokens · 7 calls · thinking…");
    expect(usageWords({ input: 900, output: 40, cached: 0, calls: 1, in_flight: false }))
      .toBe("940 tokens · 1 call");
  });

  it("says nothing before the first call", () => {
    expect(usageWords({ input: 0, output: 0, cached: 0, calls: 0, in_flight: false })).toBeNull();
  });

  it("names each call's purpose in plain words", () => {
    expect(purposeWords("goal")).toBe("reading your request");
    expect(purposeWords("gap")).toBe("reading your reply");
    expect(purposeWords("tier4")).toBe("choosing between tools");
  });
});

describe("the call panel", () => {
  beforeEach(() => vi.mocked(get).mockReset().mockResolvedValue([CALL]));

  it("asks for nothing while closed", () => {
    mount(<CallPanel sessionId="s1" calls={1} open={false} />);
    expect(get).not.toHaveBeenCalled();
  });

  it("lists each call, and shows its reply only when asked", async () => {
    mount(<CallPanel sessionId="s1" calls={1} open />);
    expect(await screen.findByText("reading your request")).toBeInTheDocument();
    expect(screen.getByText(/3,000 in · 40 out/)).toBeInTheDocument();
    expect(screen.queryByText(/counts\.matrix/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /reply/ }));
    expect(screen.getByText(/counts\.matrix/)).toBeInTheDocument();
  });

  it("does not fetch again while the count has not moved", async () => {
    const cache = new QueryClient();
    const at = (calls: number) => (
      <QueryClientProvider client={cache}>
        <CallPanel sessionId="s1" calls={calls} open />
      </QueryClientProvider>
    );
    const { rerender } = render(at(1));
    await screen.findByText("reading your request");
    rerender(at(1));
    expect(get).toHaveBeenCalledTimes(1);
    rerender(at(2));
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });
});

describe("the header's count (issue 191)", () => {
  beforeEach(() => vi.mocked(get).mockReset().mockResolvedValue([CALL]));

  it("shows the count once there are calls, and opens the list on a click", async () => {
    const { LivingHeader } = await import("./LivingHeader");
    const { FAKE_SESSION } = await import("./fake");
    const session = { ...FAKE_SESSION,
      usage: { input: 3000, output: 40, cached: 0, calls: 1, in_flight: false } };
    mount(<LivingHeader session={session} view="canvas" onView={() => {}} onRun={() => {}}
                        running={false} />);
    expect(get).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "3.0k tokens · 1 call" }));
    expect(await screen.findByText("reading your request")).toBeInTheDocument();
  });

  it("shows no count before the first call", async () => {
    const { LivingHeader } = await import("./LivingHeader");
    const { FAKE_SESSION } = await import("./fake");
    const session = { ...FAKE_SESSION,
      usage: { input: 0, output: 0, cached: 0, calls: 0, in_flight: false } };
    mount(<LivingHeader session={session} view="canvas" onView={() => {}} onRun={() => {}}
                        running={false} />);
    expect(screen.queryByRole("button", { name: /tokens/ })).toBeNull();
  });
});
