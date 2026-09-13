import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringPreview, AuthoringSession, DraftGraph } from "../../api/types";
import { useKeep } from "../useKeep";
import { ArtifactPreview } from "./ArtifactPreview";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingSurface } from "./LivingSurface";
import { useAuthoringSession } from "./useAuthoringSession";

/** Task 13: the preview the server writes, and Keep/Run over the session's own draft.
 *
 * The byte relationship between preview and kept file, preview purity and artifact reload are the
 * server's and live in `test_authoring_keep.py`. These hold the browser's half: one draft, a
 * preview asked for once per settled revision, a preview that says it is one, and a Run that is
 * disabled until something is connected to it.
 */

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const fresh = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

function wrap(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

const GRAPH: DraftGraph = { nodes: [{ id: "fastqc", contract_id: "nf-core/fastqc@0.12.1" }], edges: [] } as DraftGraph;

describe("keeping the session's own draft", () => {
  it("keeps the draft the session owns — never creating a second one or saving over it", async () => {
    const fetch = vi.fn(async () => ok({ draft_id: "d1" }));
    vi.stubGlobal("fetch", fetch);

    const { result } = renderHook(() => useKeep(GRAPH, { draftId: "d1" }), { wrapper: wrap(fresh()) });
    expect(result.current.draftId).toBe("d1");
    await act(async () => {
      await result.current.keepAsync();
    });

    const calls = fetch.mock.calls.map((call) => {
      const [url, init] = call as unknown as [string, RequestInit | undefined];
      return `${init?.method ?? "GET"} ${url}`;
    });
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatch(/^POST .*\/pipeline\/drafts\/d1\/keep$/);
    expect(result.current.blocked).toBeNull();
  });

  it("still creates a draft when the page owns none — the manual builder's path", async () => {
    const fetch = vi.fn(async (url: string) => ok(url.endsWith("/keep") ? {} : { id: "new" }));
    vi.stubGlobal("fetch", fetch);

    const { result } = renderHook(() => useKeep(GRAPH), { wrapper: wrap(fresh()) });
    await act(async () => {
      await result.current.keepAsync();
    });
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
      expect.stringMatching(/\/pipeline\/drafts$/),
      expect.stringMatching(/\/pipeline\/drafts\/new\/keep$/),
    ]);
  });
});

describe("the preview is asked for once the revision settles", () => {
  it("asks once after a burst of commits, not once per revision", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let revision = 0;
    const session = () => ({
      id: "s1", draft_id: "d1", mode: "spawn", phase: "building", failed_from: null, goal: null,
      revision, graph: { nodes: [], edges: [] }, row_version: 1, model_configured: true,
      turns: [{ seq: 0, role: "assistant", state: revision < 5 ? "pending" : "answered", text: "",
                blocks: [], base_revision: 0 }],
      pending_proposal: null,
    });
    const fetch = vi.fn(async (url: string) => {
      if (url.endsWith("/preview")) return ok({ revision, state: "empty", text: "", findings: [] });
      if (url.endsWith("/vocabulary")) return ok({ types: {} });
      const body = session();
      revision = Math.min(5, revision + 1);
      return ok(body);
    });
    vi.stubGlobal("fetch", fetch);

    renderHook(() => useAuthoringSession("s1", { pollMs: 40 }), { wrapper: wrap(fresh()) });
    // **Many short acts, not one long one.** React flushes renders when an act scope ends, so a
    // single 1.2s act collapsed six revisions into one render and this test passed with the
    // debounce deleted.
    for (let tick = 0; tick < 40; tick += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30);
      });
    }

    const previews = fetch.mock.calls.filter(([url]) => String(url).endsWith("/preview")).length;
    const reads = fetch.mock.calls.filter(([url]) => String(url).endsWith("/authoring/s1")).length;
    expect(reads).toBeGreaterThanOrEqual(6);
    expect(previews).toBe(1);
  });
});

const ready = (revision: number, text: string): AuthoringPreview =>
  ({ revision, state: "ready", text, findings: [] });

describe("ArtifactPreview", () => {
  it("says it is a preview, and not the kept artifact", () => {
    render(<ArtifactPreview preview={ready(3, "version: 6\n")} />);
    expect(screen.getByTestId("preview-label")).toHaveTextContent("revision 3 · not kept");
    expect(screen.getByTestId("artifact-text")).toHaveTextContent("version: 6");
  });

  it("shows why there is no file, never half a document", () => {
    const { rerender } = render(
      <ArtifactPreview preview={{ revision: 0, state: "empty", text: "", findings: [] }} />,
    );
    expect(screen.getByTestId("preview-empty")).toHaveTextContent("Nothing has been added yet");
    expect(screen.queryByTestId("artifact-text")).toBeNull();

    rerender(
      <ArtifactPreview preview={{ revision: 2, state: "illegal", text: "",
                                   findings: ["MD0501: star_align.reads is not connected"] }} />,
    );
    expect(screen.getByTestId("preview-illegal")).toHaveTextContent("MD0501: star_align.reads");
    expect(screen.queryByTestId("artifact-text")).toBeNull();
  });

  it("highlights the lines a revision added, then settles to ordinary text", async () => {
    vi.useFakeTimers();
    const { rerender } = render(<ArtifactPreview preview={ready(1, "version: 6\nsteps:")} />);
    expect(document.querySelectorAll("[data-changed]")).toHaveLength(0);

    rerender(<ArtifactPreview preview={ready(2, "version: 6\nsteps:\n- id: fastqc")} />);
    const changed = Array.from(document.querySelectorAll("[data-changed]")).map((n) => n.textContent);
    expect(changed).toEqual(["- id: fastqc"]);

    act(() => {
      vi.advanceTimersByTime(1700);
    });
    expect(document.querySelectorAll("[data-changed]")).toHaveLength(0);
    expect(screen.getByTestId("artifact-text")).toHaveTextContent("- id: fastqc");
  });
});

function surface(session: AuthoringSession, run: Parameters<typeof LivingSurface>[0]["run"]) {
  render(
    <QueryClientProvider client={fresh()}>
      <LivingSurface
        session={session} graph={session.graph} steps={FAKE_STEPS}
        state={{ ...initialAuthoring, snapshot: session }}
        preview={ready(session.revision, "version: 6\n")}
        busy={() => false} onAccept={vi.fn()} onReject={vi.fn()} onPreviewOption={vi.fn()}
        onSelect={vi.fn()} onCompose={vi.fn()} onSay={vi.fn()} onRetry={vi.fn()} onAddStep={vi.fn()}
        onDismiss={vi.fn()} onSetParam={vi.fn()} onApplyChange={vi.fn()}
        run={run}
      />
    </QueryClientProvider>,
  );
}

const complete = { ...FAKE_SESSION, phase: "complete", pending_proposal: null } as AuthoringSession;

describe("Run on a living pipeline", () => {
  it("is disabled when nothing is connected to it, even on a complete pipeline", () => {
    surface(complete, null);
    expect(screen.getByTestId("living-run")).toBeDisabled();
  });

  it("runs the keep → lint → sheet sequence it is given, and shows a coded refusal", () => {
    const onRun = vi.fn();
    surface(complete, { onRun, busy: false, stage: null, kept: false, sheet: null,
                        error: "MD0502: the draft is not a legal pipeline" });
    fireEvent.click(screen.getByTestId("living-run"));
    expect(onRun).toHaveBeenCalledOnce();
    expect(screen.getByTestId("living-run-error")).toHaveTextContent("MD0502");
  });

  it("stays disabled until the pipeline is complete", () => {
    surface(FAKE_SESSION, { onRun: vi.fn(), busy: false, stage: null, error: null, kept: false, sheet: null });
    expect(screen.getByTestId("living-run")).toBeDisabled();
  });

  it("offers the kept file only once something was kept", () => {
    surface(complete, { onRun: vi.fn(), busy: false, stage: null, error: null, kept: false, sheet: null });
    fireEvent.click(screen.getByTestId("living-view-artifact"));
    expect(screen.getByTestId("artifact-tab-kept")).toBeDisabled();
    expect(screen.getByTestId("preview-label")).toHaveTextContent("not kept");
  });
});
