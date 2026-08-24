import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { SubmitPanel } from "./Submit";

/** The courier — A179, `docs/design/wiener.md` §12.
 *
 * These are about the two things the panel is *for*: that it will not offer a run until a gate
 * has proved the artifact, and that the parameters it asks for are the artifact's own rather
 * than a guess. Both are rules a screenshot cannot check.
 */

function show(node: React.ReactElement) {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const STORED = {
  artifact_id: "a".repeat(32),
  digest: "sha256:" + "b".repeat(64),
  size_bytes: 51_200,
  declared: ["fasta", "gtf", "input"],
};

function uploads(stored = STORED) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    json: async () => stored,
    blob: async () => new Blob(["zip"]),
  });
}

describe("what it refuses to offer", () => {
  it("will not send a pipeline that was never kept", () => {
    show(<SubmitPanel draftId={null} gated={false} />);
    expect(screen.getByTestId("send-to-wiener")).toBeDisabled();
    expect(screen.getByText(/keep this pipeline first/i)).toBeTruthy();
  });

  it("will not run a pipeline no gate has passed, and says why in words", () => {
    // `execution-boundary.md` §3: a gate proves the artifact on public data; a run spends a
    // laboratory's time on its own. The order is not decoration.
    show(<SubmitPanel draftId="abc" gated={false} />);
    expect(screen.getByTestId("send-to-wiener")).toBeDisabled();
    expect(screen.getByText(/gate it first/i)).toBeTruthy();
  });

  it("offers it once a gate has passed", () => {
    show(<SubmitPanel draftId="abc" gated />);
    expect(screen.getByTestId("send-to-wiener")).not.toBeDisabled();
  });
});

describe("the artifact is the schema", () => {
  it("asks for exactly the parameters the upload declared", async () => {
    // §12: Mendel emits every value it can justify and `null` for every value only the
    // laboratory can supply. The form is that list, not a `samplesheet` field somebody chose.
    vi.stubGlobal("fetch", uploads());
    show(<SubmitPanel draftId="abc" gated />);
    screen.getByTestId("send-to-wiener").click();

    await waitFor(() => expect(screen.getByTestId("param-input")).toBeTruthy());
    expect(screen.getByTestId("param-fasta")).toBeTruthy();
    expect(screen.getByTestId("param-gtf")).toBeTruthy();
  });

  it("will not submit while a declared parameter is empty", async () => {
    // Wiener refuses a partial map and says which keys are missing. The button says it first:
    // a refusal a disabled control could have prevented is a round trip to learn something the
    // page already knew.
    vi.stubGlobal("fetch", uploads());
    show(<SubmitPanel draftId="abc" gated />);
    screen.getByTestId("send-to-wiener").click();

    await waitFor(() => expect(screen.getByTestId("start-run")).toBeDisabled());
    expect(screen.getByTestId("start-run").title).toMatch(/fasta, gtf, input/);
  });

  it("asks for nothing when the artifact declares nothing", async () => {
    vi.stubGlobal("fetch", uploads({ ...STORED, declared: [] }));
    show(<SubmitPanel draftId="abc" gated />);
    screen.getByTestId("send-to-wiener").click();

    await waitFor(() => expect(screen.getByText(/asks for nothing/i)).toBeTruthy());
    expect(screen.getByTestId("start-run")).not.toBeDisabled();
  });
});

describe("when Wiener wants a token", () => {
  it("offers a field rather than a status code", async () => {
    // §12.1's check is one shared bearer token, and the failure a person meets is a 401. The
    // page that meets it is the page that should be able to fix it.
    // **Mendel answers and Wiener refuses**, which is the real shape: `mendel-api` has no
    // token and `wiener-api` does. A mock that 401s both would pass on a panel that never
    // reached Wiener at all.
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        String(url).startsWith("/api/artifacts")
          ? { ok: false, status: 401, json: async () => ({}) }
          : { ok: true, status: 200, blob: async () => new Blob(["zip"]) },
      ),
    ));
    show(<SubmitPanel draftId="abc" gated />);
    screen.getByTestId("send-to-wiener").click();

    await waitFor(() => expect(screen.getByTestId("token-prompt")).toBeTruthy());
  });
});
