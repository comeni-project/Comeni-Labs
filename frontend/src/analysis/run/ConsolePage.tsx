import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { post } from "../../api/client";
import { ShellContext } from "../../build/living/AgentThread";
import { ChatPanel } from "../../build/living/ChatPanel";
import { useAuthoringSession } from "../../build/living/useAuthoringSession";
import { useAiConfigured } from "../../home/useAiConfigured";
import { get as fromWiener, post as toWiener } from "../../wiener/api/client";
import { Commands, type Command } from "./Commands";
import { TERMINAL, type Task } from "./model";
import { Terminal, type TerminalHandle } from "./Terminal";
import { factsOf, useBuildCanvas, useRun } from "./useRuns";


const PANE = "flex items-center gap-[10px] px-[14px] py-[9px] bg-surface-2 border-b border-line-soft";
const QUIET = "h-7 px-[10px] rounded-control border border-line-2 bg-surface text-[12px] font-medium text-ink-2 cursor-pointer hover:text-ink";

/** Run's Console (#511, board `2026-11-16-run-console-board`): Nextflow's own terminal, live; a
 *  shell in the run's folder; Commands; and the assistant, which sees both.
 *
 * The shell is host-level control behind the Wiener token (#525). The assistant runs only
 * read-only commands, through Wiener's check (`/terminal/exec`), and the page carries what the
 * console showed to it — Mendel never reaches Wiener (A179). */
export function ConsolePage({ draftId, runId, phase }: { draftId: string; runId: string; phase: string }) {
  const nextflow = useRef<TerminalHandle>(null);
  const shell = useRef<TerminalHandle>(null);
  const [cwd, setCwd] = useState("");
  const [shellKey, setShellKey] = useState(0);
  const [commands, setCommands] = useState(false);
  const [assistant, setAssistant] = useState(phase === "failed");
  const [split, setSplit] = useState(0.52);
  const [live, setLive] = useState<"connecting" | "open" | "closed">("connecting");
  const area = useRef<HTMLDivElement>(null);
  const over = TERMINAL.has(phase);
  const base = `/api/runs/${encodeURIComponent(runId)}/terminal`;

  const failed = useFailure(draftId, runId, phase === "failed");
  const list = useQuery({
    queryKey: ["terminal-commands", runId],
    queryFn: () => fromWiener<{ commands: Command[] }>(`${base}/commands`),
  });
  const resume = list.data?.commands.find((c) => c.name === "Resume the run")?.command;

  const dragSplit = (e: React.PointerEvent) => {
    const box = area.current?.getBoundingClientRect();
    if (!box) return;
    (e.target as Element).setPointerCapture(e.pointerId);
    const move = (m: PointerEvent) => setSplit(Math.min(0.8, Math.max(0.2, (m.clientY - box.top) / box.height)));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <ShellContext.Provider value={{ run: (c) => shell.current?.run(c), insert: (c) => shell.current?.insert(c) }}>
      {failed && (
        <div role="status" className="flex flex-wrap items-center gap-3 px-[14px] py-[10px] rounded-panel bg-needs-you-soft border border-needs-you-line">
          <span aria-hidden className="w-2 h-2 rounded-full bg-needs-you shrink-0" />
          <span className="flex-1 min-w-[240px] text-[13.5px] text-ink">
            <b>{failed.step}{failed.tag ? ` · ${failed.tag}` : ""}</b> stopped{failed.exit != null ? `: exit ${failed.exit}` : ""}
            {failed.exit === 137 ? ", it ran out of memory." : "."}
          </span>
          {failed.folder && (
            <button type="button" className={QUIET} onClick={() => { setCwd(failed.folder!); setShellKey((k) => k + 1); }}>
              Open its folder in the shell
            </button>
          )}
          {resume && (
            <button type="button" onClick={() => shell.current?.run(resume)}
                    className="h-8 px-[14px] rounded-control border-0 bg-action text-on-action shadow-raise text-[13px] font-semibold cursor-pointer">
              Resume the run
            </button>
          )}
        </div>
      )}
      <div className="flex-1 min-h-[560px] flex gap-3">
        <section ref={area} aria-label="Console" className="flex-1 min-w-0 flex flex-col rounded-panel border border-line bg-surface overflow-hidden">
          <div className={PANE}>
            <span className="text-[13px] font-semibold text-ink">Nextflow</span>
            <span className={`flex items-center gap-[6px] text-[12px] ${over ? "text-ink-3" : "text-now-ink"}`}>
              {!over && <span aria-hidden className="w-[6px] h-[6px] rounded-full bg-now" />}
              {over ? "the run is over · replayed from console.log" : live === "open" ? "live · following" : "connecting…"}
            </span>
            <span className="ml-auto flex gap-[6px]">
              <button type="button" className={QUIET} onClick={() => void navigator.clipboard?.writeText(nextflow.current?.tail(5000) ?? "")}>Copy</button>
              <button type="button" className={`${QUIET} ${assistant ? "border-ai-line text-ai" : ""}`} onClick={() => setAssistant(!assistant)}
                      aria-pressed={assistant}>Assistant</button>
            </span>
          </div>
          <div className="flex flex-col min-h-0" style={{ flex: split }}>
            <Terminal ref={nextflow} path={`${base}/console`} label="What Nextflow printed" onState={setLive} />
          </div>
          <div role="separator" aria-orientation="horizontal" aria-label="Resize the panes" onPointerDown={dragSplit}
               className="h-[9px] shrink-0 flex items-center justify-center bg-surface-2 border-y border-line-soft cursor-row-resize touch-none">
            <span aria-hidden className="w-9 h-[3px] rounded-full bg-line-2" />
          </div>
          <div className={PANE}>
            <span className="text-[13px] font-semibold text-ink">Shell</span>
            <span className="font-data text-[11.5px] text-ink-3 truncate">in runs/{runId.slice(0, 8)}{cwd ? `/${cwd}` : ""}</span>
            <span title="This shell can use Docker on this machine, which is full control of it"
                  className="px-2 py-[2px] rounded-control bg-measured-soft text-measured-ink text-[11.5px] font-semibold whitespace-nowrap">
              full access to this machine
            </span>
            <span className="ml-auto flex gap-[6px]">
              <button type="button" onClick={() => setCommands(true)}
                      className={`${QUIET} flex items-center gap-[6px] text-ink font-semibold`}>
                <svg aria-hidden width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5 14 14" /></svg>
                Commands
              </button>
              {cwd && <button type="button" className={QUIET} onClick={() => { setCwd(""); setShellKey((k) => k + 1); }}>Back to the run folder</button>}
              <button type="button" className={QUIET} onClick={() => setShellKey((k) => k + 1)}>New shell</button>
            </span>
          </div>
          <div className="flex flex-col min-h-0" style={{ flex: 1 - split }}>
            <Terminal key={`${shellKey}:${cwd}`} ref={shell} interactive label="Shell in the run's folder"
                      path={`${base}/shell${cwd ? `?cwd=${encodeURIComponent(cwd)}` : ""}`} />
          </div>
        </section>
        {assistant && (
          <ConsoleAssistant draftId={draftId} runId={runId} cwd={cwd} base={base}
                            shell={shell} onClose={() => setAssistant(false)} />
        )}
      </div>
      {commands && (
        <Commands runId={runId} onClose={() => setCommands(false)}
                  onInsert={(c) => shell.current?.insert(c)} onRun={(c) => shell.current?.run(c)} />
      )}
    </ShellContext.Provider>
  );
}

/** The failed step of a failed run, and its task's folder from Nextflow's own error (`Work dir:`). */
function useFailure(draftId: string, runId: string, enabled: boolean) {
  const run = useRun(runId);
  const facts = factsOf(useBuildCanvas(draftId).data);
  const failed = useQuery({
    queryKey: ["failed-tasks", runId, "first"],
    queryFn: () => fromWiener<{ tasks: Task[] }>(`/api/runs/${runId}/tasks?status=FAILED&limit=1`),
    enabled,
  });
  const text = useQuery({
    queryKey: ["console-text", runId],
    queryFn: () => fromWiener<{ text: string }>(`/api/runs/${runId}/terminal/console?lines=400`),
    enabled,
  });
  const task = failed.data?.tasks?.[0];
  // A failure we cannot read is no banner: the console below still shows Nextflow's error.
  if (!enabled || !task || failed.isError) return null;
  const node = (run.graph.data?.nodes ?? []).find((n) => n.process === task.process);
  const dir = /Work dir:\s*\n\s*(\S+)/.exec(text.data?.text ?? "")?.[1];
  return {
    step: facts[node?.id ?? ""]?.does ?? task.process,
    tag: task.tag,
    exit: task.latest_exit ?? null,
    folder: dir && dir.includes("/work/") ? `work/${dir.split("/work/")[1]}` : null,
  };
}

/** The assistant beside the console: the analysis's conversation, given what the console and the
 *  shell show with each message. A read-only command it suggests the page runs through Wiener's
 *  check, notes in the shell, and sends back; any other it only suggests. */
function ConsoleAssistant({ draftId, runId, cwd, base, shell, onClose }: {
  draftId: string; runId: string; cwd: string; base: string;
  shell: React.RefObject<TerminalHandle | null>; onClose: () => void;
}) {
  const model = useAiConfigured();
  const opened = useQuery({
    queryKey: ["session-of", draftId],
    queryFn: () => post<{ session_id: string }>(`/pipeline/drafts/${encodeURIComponent(draftId)}/session`, {}),
    staleTime: Infinity,
  });
  return (
    <aside aria-label="Assistant" className="w-[380px] shrink-0 flex flex-col rounded-panel border border-line bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-[14px] py-[11px] border-b border-line-soft">
        <span className="text-[13.5px] font-semibold text-ink">Assistant</span>
        <span className="text-[12px] text-ink-3">sees the console and the shell</span>
        <button type="button" aria-label="Close the assistant" onClick={onClose}
                className="ml-auto w-7 h-7 border-0 rounded-control bg-transparent text-ink-3 text-[16px] cursor-pointer">×</button>
      </div>
      {model.pending || opened.isPending ? <p className="m-4 text-[13px] text-ink-3">Opening…</p>
        : !model.configured ? <p className="m-4 text-[13px] text-ink-2">Connect a model in Settings to ask about this run.</p>
        : opened.data ? <Talk sessionId={opened.data.session_id} runId={runId} cwd={cwd} base={base} shell={shell} />
        : <p className="m-4 text-[13px] text-needs-you-ink">The conversation could not open.</p>}
    </aside>
  );
}

const AUTO_RUNS = 3;

/** **What the page runs for the assistant by itself** (Checkpoint D): read-only commands it has
 *  not run yet, at most `AUTO_RUNS`, and only in a reply to something the person said — never in
 *  a reply to the output it sent back itself, so one message from the person is one round. */
export function autoRuns(blocks: { id: string; kind: string; read_only?: boolean | null; command?: string }[],
                         handled: Set<string>, personAsked: boolean): { id: string; command: string }[] {
  if (!personAsked) return [];
  return blocks.filter((b) => b.kind === "command" && b.read_only && !handled.has(b.id))
    .slice(0, AUTO_RUNS) as { id: string; command: string }[];
}

function Talk({ sessionId, runId, cwd, base, shell }: {
  sessionId: string; runId: string; cwd: string; base: string; shell: React.RefObject<TerminalHandle | null>;
}) {
  const living = useAuthoringSession(sessionId, { pollMs: 1500 });
  const handled = useRef<Set<string> | null>(null);
  // Set when the person sends a message; spent by the one round of runs that answers it.
  const asked = useRef(false);
  const turns = living.session?.turns ?? [];
  if (handled.current === null && living.session) {
    // What was suggested before the page opened was handled then.
    handled.current = new Set(turns.flatMap((t) => t.blocks.filter((b) => b.kind === "command").map((b) => b.id)));
  }
  const context = async () => ({
    run: runId,
    // Within what the server takes (40,000 and 20,000 characters), the newest kept.
    console: (await fromWiener<{ text: string }>(`${base}/console?lines=200`).catch(() => ({ text: "" }))).text.slice(-38_000),
    shell: (shell.current?.tail(80) ?? "").slice(-18_000),
  });
  const last = turns.at(-1);
  useEffect(() => {
    if (!last || last.role !== "assistant" || last.state !== "answered" || !handled.current) return;
    const todo = autoRuns(last.blocks as Parameters<typeof autoRuns>[0], handled.current, asked.current);
    if (todo.length === 0) return;
    asked.current = false;
    todo.forEach((b) => handled.current!.add(b.id));
    void (async () => {
      const outputs: string[] = [];
      for (const b of todo) {
        const ran = await toWiener<{ output: string; exit: number }>(`${base}/exec`, { command: b.command, cwd })
          .catch((e: unknown) => ({ output: e instanceof Error ? e.message : String(e), exit: -1 }));
        shell.current?.note(`\x1b[35mAI ran\x1b[0m ${b.command}\n${ran.output.trimEnd()}`);
        outputs.push(`$ ${b.command}\n${ran.output.trimEnd()}`);
      }
      const seen = await context();
      living.sayWith(`Ran ${todo.map((b) => b.command).join("; ")} for the assistant.`,
                     { ...seen, shell: outputs.join("\n\n").slice(-6000) });
    })();
  }, [last?.seq, last?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!living.session) return <p className="m-4 text-[13px] text-ink-3">Opening the conversation…</p>;
  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <ChatPanel embedded session={living.session} sending={living.sending} composer={living.composer}
                 onCompose={living.compose}
                 onSay={(text) => { asked.current = true; void context().then((seen) => living.sayWith(text, seen)); }}
                 onAnswer={living.answer} onRetry={living.retry} notices={null} />
    </div>
  );
}
