import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../../api/client";

import { processName } from "./format";
import { StepCard, hasInputs, type CardKind } from "./StepCard";
import { StepMenu, type MenuItem } from "./StepMenu";

import type { AuthoringSession, DraftGraph } from "../../api/types";
import type { components } from "../../api/schema";
import { AddStep } from "../../analysis/build/AddStep";
import type { Positions } from "../geometry";
import { idFor } from "../graphOps";
import { type AnsweredStep, withTypedValues } from "../useBuilder";
import type { AnswerValue } from "./AgentQuestion";
import { ChatPanel } from "./ChatPanel";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";
import type { ReviewState } from "./LivingNode";
import { PipelineFile } from "./PipelineFile";
import type { ServerNotice } from "./useAuthoringSession";
import { useFocus } from "./useFocus";
import { SidePanel, type SideTab } from "../../analysis/build/SidePanel";
import { RailControls } from "../../app/rail/RailContext";
import { open as isOpen } from "../useBuilder";
import { type InputFrom, ToolForm } from "../../analysis/build/ToolForm";
import { valuesOf } from "./values";

/** The builder's composition (#463): **wires state and callbacks, draws nothing itself.**
 *
 * The canvas beside the conversation with the agent. The canvas is the
 * pipeline as it stands from the first message: empty until the agent builds, then each step as
 * it lands. The panel's widths are the artboards' (`.living` in `main.css`): 420px, 360px under
 * 1180px, and stacked under 1000px with the conversation first *visually* while the canvas stays
 * first in the document for a screen reader. The panel stacks; it never overlays the graph.
 */
export function LivingSurface({
  session, graph, preview, selected, onSelect, composer, onCompose, sending, onSay, onAnswer, onRetry,
  onReviewed, notice = null, onDismiss, onSetParam, onSwitchInput, onWhole, onEdit, onAddStep,
  onRename, run = null,
}: {
  session: AuthoringSession;
  /** The draft as saved — what an edit changes. The canvas draws the session's frame. */
  graph: DraftGraph;
  preview: components["schemas"]["AuthoringPreview"] | null;
  selected: string | null;
  onSelect: (node: string | null) => void;
  composer: string;
  onCompose: (text: string) => void;
  sending: string[];
  onSay: (text: string) => void;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onReviewed: (node: string) => void;
  notice?: ServerNotice | null;
  onDismiss: () => void;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onSwitchInput?: (contract: string, port: string, state: "off" | "optional" | "required") => void;
  onWhole?: (contract: string, whole: boolean) => void;
  /** A direct change to the drawn pipeline, as the whole next graph — the person's. */
  onEdit: (graph: DraftGraph) => void;
  onAddStep: (contractId: string) => void;
  onRename?: (name: string) => void;
  /** The Run sequence — keep, lint, run sheet — when the page has one. The fixtures do not. */
  run?: {
    onRun: () => void;
    busy: boolean;
    stage: string | null;
    error: string | null;
    kept: boolean;
    sheet: React.ReactNode;
  } | null;
}) {
  const [view, setView] = useState<"canvas" | "artifact">("canvas");
  const [browsing, setBrowsing] = useState(false);
  const [pane, setPane] = useState<"chat" | "canvas">("chat");
  const [tab, setTab] = useState<SideTab>(selected ? "step" : "assistant");
  // The analysis's kept samples: a per-sample step reads ×N, a fan-in port *all N*.
  const data = useQuery({
    queryKey: ["analysis-data", session.draft_id],
    queryFn: () => get<{ samples?: { left_out?: boolean }[] }>(`/data/${encodeURIComponent(session.draft_id)}`),
    retry: false,
  });
  const kept = data.data?.samples?.filter((s) => !s.left_out).length;
  // Where *Add step here* asked the next step to go, and the steps placed so.
  const [addAt, setAddAt] = useState<{ x: number; y: number } | null>(null);
  const [placed, setPlaced] = useState<Record<string, { x: number; y: number }>>({});
  const [connect, setConnect] = useState<{ node: string; port: string } | null>(null);

  // **The server's frame, whole**: the visible graph, each step's recorded metadata, and the
  // channels that really enter. Nothing here re-derives or guesses any of it.
  const frame = session.canvas ?? null;
  const answered = (frame?.steps ?? []).map((step) => withTypedValues(step, graph));
  const steps: Record<string, AnsweredStep> = Object.fromEntries(answered.map((step) => [step.id, step]));
  const values = valuesOf(answered);
  const aiChosen = [...new Set(session.ai_unreviewed.map((c) => c.node))].sort();
  const reviews: Record<string, ReviewState> = {};

  // **A step the agent just built is brought on screen**, as the person's selection is.
  const [newest, setNewest] = useState<string | null>(null);
  const ids = (frame?.graph.nodes ?? []).map((n) => n.id).join(",");
  const [seen, setSeen] = useState(ids);
  if (ids !== seen) {
    const before = new Set(seen.split(","));
    setNewest(ids.split(",").find((id) => id && !before.has(id)) ?? null);
    setSeen(ids);
  }
  const focus = useFocus(newest, selected);

  // **One thing beside a step at a time** (#499): its menu, or one of its cards. A click opens
  // the step's Settings card; the menu chooses another. Neither covers the conversation.
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [fileStep, setFileStep] = useState<string | null>(null);
  const [kind, setKind] = useState<CardKind>("settings");
  const present = (node: string | null) => node !== null && graph.nodes.some((n) => n.id === node);
  const [cardFor, setCardFor] = useState<string | null>(selected);
  const [was, setWas] = useState(selected);
  if (selected !== was) { setWas(selected); setCardFor(selected); }
  const carded = present(cardFor) ? cardFor : null;
  const pick = (node: string | null) => {
    setMenuFor(null); setCardFor(node); setKind("settings"); onSelect(node);
    if (node) setTab("step");
  };
  // Focus goes back to the step the menu or card belonged to; it is still drawn when they close.
  const backTo = (node: string) => document.querySelector<HTMLElement>(`[data-node="${node}"]`)?.focus();
  const closeMenu = (node: string) => { setMenuFor(null); backTo(node); };
  const openCard = (node: string, next: CardKind) => {
    setMenuFor(null); setCardFor(node); setKind(next); onSelect(node);
    if (next === "settings") setTab("step");
  };
  const closeCard = () => { const at = carded; pick(null); if (at) backTo(at); };
  const aiAt = (node: string) => session.ai_unreviewed.filter((c) => c.node === node)
    .map((c) => ({ what: c.what, because: c.because }));
  const menuItems = (node: string): MenuItem[] => [
    { id: "ask", label: "Ask about this step" },
    { id: "settings", label: "Settings…" },
    ...(hasInputs(steps[node]) ? [{ id: "inputs", label: "Inputs…" }] : []),
    { id: "swap", label: "Swap tool…" },
    { id: "file", label: "Show in pipeline file" },
    ...(steps[node]?.parts ? [{ id: "whole", label: steps[node].parts!.on ? "Keep whole" : "Run on parts" }] : []),
    ...(aiAt(node).length > 0 ? [{ id: "reviewed", label: "Looks right" }] : []),
    { id: "remove", label: "Remove step…", danger: true },
  ];
  const choose = (node: string, item: string) => {
    if (item === "settings" || item === "inputs" || item === "swap" || item === "remove") {
      openCard(node, item);
      return;
    }
    closeMenu(node);
    if (item === "ask") { setPane("chat"); setTab("assistant"); onCompose(`About ${processName(node)}: `); }
    else if (item === "file") { setFileStep(node); setView("artifact"); }
    else if (item === "reviewed") onReviewed(node);
    else if (item === "whole" && steps[node]?.parts) onWhole?.(steps[node].contract_id, steps[node].parts!.on);
  };
  const beside = menuFor && present(menuFor) ? {
    node: menuFor,
    content: <StepMenu label={`${processName(menuFor)} menu`} items={menuItems(menuFor)}
                       onChoose={(item) => choose(menuFor, item)} onClose={() => closeMenu(menuFor)} />,
  } : carded && kind !== "settings" ? {
    node: carded,
    content: (
      <div className="px-4 py-3 rounded-panel border shadow-raise"
           style={{ background: "var(--surface)", borderColor: "var(--line-2)" }}>
        <StepCard node={carded} kind={kind} onKind={setKind} step={steps[carded]} graph={graph}
                  onSetParam={onSetParam} onEdit={onEdit} onClose={closeCard} onSwitchInput={onSwitchInput}
                  onWhole={onWhole} aiChoices={aiAt(carded)} onReviewed={onReviewed} />
      </div>
    ),
  } : null;

  const notices = (
    <>
      {notice && (
        <div role="alert" data-testid="living-notice"
             className="mx-4 mt-4 px-3 py-2 border rounded-button flex items-baseline gap-3"
             style={{ borderColor: "var(--needs-you)", background: "var(--needs-you-soft)" }}>
          <span className="text-[12.5px] text-ink flex-1">{notice.text}</span>
          {notice.code && <span className="font-data text-[10px] text-ink-2">{notice.code}</span>}
          <button type="button" onClick={onDismiss}
                  className="bg-transparent border-0 text-ink-2 cursor-pointer text-[11px]">
            Dismiss
          </button>
        </div>
      )}
      {session.retired && <p className="mx-4 mt-4 text-[12px] text-ink-2">
        This archived conversation is read-only. <a href="/build" className="text-now-ink underline">Start a new analysis</a>.
      </p>}
      {!session.model_configured && (
        <div data-testid="no-model" className="mx-4 mt-4">
          <p className="m-0 text-[13px] text-ink">No model is configured here</p>
          <p className="m-0 mt-1 text-[12.5px] text-ink-2">
            The builder agent needs one. Everything else works: draw the pipeline yourself on the
            canvas, and the engine settles every step it can prove.
          </p>
        </div>
      )}
    </>
  );

  const talk = { session, sending, composer, onCompose, onSay, onAnswer, onRetry, notices: null };
  const chosen = carded ?? (present(selected) ? selected : null);
  const runnable = run !== null && !session.retired;

  // **Review**, in the rail: each step the AI chose for and nobody reviewed, and each value that
  // still needs the person. A click opens that step.
  const review = [
    ...aiChosen.map((node) => ({ node, tag: "AI", what: aiAt(node).map((c) => c.what).join("; ") })),
    ...answered.flatMap((step) => step.settings.filter(isOpen)
      .map((s) => ({ node: step.id, tag: "needs you", what: s.name }))),
  ];

  return (
    <div className="grid grid-rows-[auto_1fr] h-full overflow-hidden" data-testid="living">
      {review.length > 0 && (
        <RailControls label="Review">
          <ul className="list-none m-0 p-0 flex flex-col">
            {review.map((r) => (
              <li key={`${r.tag}-${r.node}-${r.what}`}>
                <button type="button" onClick={() => pick(r.node)}
                        className="w-full flex items-baseline gap-2 px-[10px] py-[5px] border-0 bg-transparent rounded-control
                                   text-left cursor-pointer hover:bg-surface-2">
                  <span className={`shrink-0 text-[10.5px] font-bold ${r.tag === "AI" ? "text-ai" : "text-needs-you-ink"}`}>
                    {r.tag === "AI" ? "AI" : "!"}
                  </span>
                  <span className="min-w-0 flex flex-col">
                    <span className="font-data text-[12px] font-medium text-ink truncate">{processName(r.node)}</span>
                    <span className="text-[11.5px] text-ink-3 truncate">{r.what}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </RailControls>
      )}
      <LivingHeader
        session={session}
        view={view}
        onView={setView}
        onRun={run ? run.onRun : () => setView("artifact")}
        running={run ? run.busy : false}
        stage={run?.stage ?? null}
        runError={run?.error ?? null}
        runnable={runnable}
        openValues={values.open}
        onRename={session.retired ? undefined : onRename}
      />
      {/* **On a phone, one pane at a time**: the conversation first. Hidden above 640px. */}
      <div role="tablist" aria-label="on a phone" className="phone-tabs gap-1 px-[16px] pt-[8px]">
        {(["chat", "canvas"] as const).map((name) => (
          <button key={name} type="button" role="tab" aria-selected={pane === name}
                  onClick={() => setPane(name)}
                  className="flex-1 px-2 py-[5px] rounded-button border text-[12px] cursor-pointer"
                  style={pane === name ? { background: "var(--now-soft)", borderColor: "var(--now-line)", color: "var(--now-ink)" }
                    : { background: "transparent", borderColor: "var(--line)", color: "var(--ink-2)" }}>
            {PANE_WORDS[name]}
          </button>
        ))}
      </div>
      {run?.sheet}
      {view === "artifact" && !run?.sheet && (
        <div className="min-h-0" style={{ borderTop: "1px solid var(--line)" }}>
          <PipelineFile steps={answered} preview={preview} draftId={session.draft_id} kept={run?.kept ?? false}
                        focusStep={fileStep}
                        onChange={(node) => { setView("canvas"); setPane("canvas"); pick(node); }}
                        onAsk={onCompose} onSay={onSay}
                        aside={<ChatPanel {...talk} embedded onStep={setFileStep} />} />
        </div>
      )}
      {/* **Kept mounted while the pipeline file or the run sheet shows**, so the canvas's view is as
          it was. Hidden by an inline style: `.living` sets `display: grid` and would win over a class. */}
      <div className="living min-h-0" data-pane={pane}
           inert={view === "artifact" || run?.sheet ? true : undefined}
           style={{ display: view === "artifact" || run?.sheet ? "none" : undefined }}>
        <section aria-label="pipeline canvas"
                 className="living-canvas relative flex flex-col min-h-0 ml-[28px] mr-[8px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden">
          <div className="relative flex-1 min-h-0 flex flex-col" data-testid="build-canvas">
            <LivingCanvas
              shown={`${pane}:${view}`}
              graph={frame?.graph ?? { nodes: [], edges: [] }}
              stale={frame !== null && !frame.current}
              working={session.working}
              reviews={reviews}
              aiChosen={aiChosen}
              channels={frame?.channels ?? []}
              positions={{ ...session.placement, ...(frame?.placement as Positions | undefined), ...placed }}
              steps={steps}
              authors={{}}
              selected={carded ?? (present(selected) ? selected : null)}
              onSelect={pick}
              focus={focus}
              onEdit={session.retired ? undefined : onEdit}
              onMenu={session.retired ? undefined : (node) => { setCardFor(null); setMenuFor(node); }}
              beside={beside}
              samples={kept || undefined}
              onAddHere={session.retired ? undefined : (at) => { setAddAt(at); setBrowsing(true); }}
              connect={connect}
              onConnected={() => setConnect(null)}
              footer={
                <button type="button" data-testid="add-step" onClick={() => setBrowsing(true)}
                        className="px-[14px] py-[6px] rounded-button border border-line-2 bg-surface text-[13px]
                                   font-semibold text-now-ink cursor-pointer hover:bg-[var(--hover)]
                                   focus-visible:shadow-[var(--ring)]">
                  + Add step
                </button>
              }
            />
          </div>
          {browsing && (
            <AddStep onAdd={(contract) => {
                       if (addAt) setPlaced({ ...placed, [idFor(graph, contract)]: addAt });
                       onAddStep(contract); setBrowsing(false); setAddAt(null);
                     }}
                     onClose={() => { setBrowsing(false); setAddAt(null); }} />
          )}
        </section>

        <SidePanel tab={tab} onTab={setTab}
                   step={chosen && steps[chosen] ? (
                     <>
                       <header className="flex flex-col gap-2 px-5 pt-4 pb-3">
                         <h2 className="m-0 text-[16px] font-semibold text-ink">
                           {steps[chosen].does ?? processName(chosen)}
                         </h2>
                         <span className="flex items-baseline gap-2 text-[12px] text-ink-3">
                           {steps[chosen].does && <span className="font-data text-ink-2">{processName(chosen)}</span>}
                           <span className="font-data">{steps[chosen].contract_id.split("@")[1]}</span>
                           <span>· {steps[chosen].runs === "per_item" ? `once per sample${kept ? ` · ×${kept}` : ""}` : "once"}</span>
                         </span>
                         {!session.retired && (
                           <div className="flex gap-2">
                             {(["swap", "remove"] as const).map((k) => (
                               <button key={k} type="button" onClick={() => openCard(chosen, k)}
                                       className="px-3 py-[4px] rounded-button border border-line bg-surface text-[12.5px]
                                                  text-ink cursor-pointer hover:bg-hover">
                                 {k === "swap" ? "Swap tool" : "Remove"}
                               </button>
                             ))}
                           </div>
                         )}
                       </header>
                       {aiAt(chosen).some((c) => !c.what.startsWith("set ")) && (
                         <section aria-label="What the AI chose"
                                  className="mx-5 mb-3 px-3 py-2 rounded-control border border-ai-line bg-ai-soft flex flex-col gap-1">
                           {aiAt(chosen).filter((c) => !c.what.startsWith("set ")).map((c) => (
                             <p key={c.what} className="m-0 text-[12.5px] text-ink">
                               <span className="font-semibold text-ai">AI</span> {c.what}
                               {c.because && <span className="block text-ink-2">{c.because}</span>}
                             </p>
                           ))}
                           <button type="button" onClick={() => onReviewed(chosen)}
                                   className="self-start px-3 py-[3px] rounded-button border border-line bg-surface text-[12px]
                                              font-medium cursor-pointer">
                             Looks right
                           </button>
                         </section>
                       )}
                       <ToolForm step={steps[chosen]} aiChoices={aiAt(chosen)}
                                 inputs={inputsOf(chosen, steps, frame, session.draft_id)}
                                 onSet={(setting, value) => onSetParam(chosen, setting, value)}
                                 onAsk={(setting) => {
                                   setTab("assistant"); setPane("chat");
                                   onSay(`About ${processName(chosen)}, the setting ${setting}: what should it be, and why?`);
                                 }}
                                 onAccept={() => onReviewed(chosen)}
                                 onConnect={session.retired ? undefined : (port) => {
                                   setPane("canvas"); setConnect({ node: chosen, port });
                                 }} />
                     </>
                   ) : (
                     <p className="m-0 px-5 py-6 text-[13px] text-ink-3">Pick a step on the canvas to see its settings.</p>
                   )}
                   assistant={<ChatPanel {...talk} notices={notices} embedded
                                         onStep={(node) => { setPane("canvas"); pick(node); }} />} />
      </div>
    </div>
  );
}

const PANE_WORDS = { chat: "Chat", canvas: "Canvas" } as const;

/** Where each of a step's inputs comes from: a Data table (an entry channel), another step, or
 *  nothing yet. Never a path. */
function inputsOf(node: string, steps: Record<string, AnsweredStep>,
                  frame: AuthoringSession["canvas"] | null, draftId: string): InputFrom[] {
  const data = `/a/${encodeURIComponent(draftId)}/data`;
  return (steps[node]?.ports ?? []).filter((p) => p.side === "in").map((p) => {
    const channel = (frame?.channels ?? []).find((c) => c.ports.includes(`${node}.${p.name}`));
    if (channel) {
      return channel.grain === "sample"
        ? { port: p.name, from: { data: "Samples", count: channel.count, href: `${data}/samples` } }
        : { port: p.name, from: { data: "References", href: `${data}/references` } };
    }
    const edge = (frame?.graph.edges ?? []).find((e) => e.to_node === node && e.to_port === p.name);
    return edge ? { port: p.name, from: { step: processName(edge.from_node) } } : { port: p.name, from: { none: true as const } };
  });
}
