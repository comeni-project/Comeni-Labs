import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import type { AuthoringPreview } from "../../api/types";
import { ArtifactView } from "../ArtifactView";
import { open as open_, optionalOpen, type Answered, type AnsweredStep } from "../useBuilder";
import { useTiers } from "../useTiers";
import { ArtifactPreview } from "./ArtifactPreview";
import { FileView, type LineDecoration } from "./FileView";
import { Secondary } from "./blocks/parts";
import { fileLines } from "./fileLines";
import { MARK_STYLE, markOf } from "./valueMarks";
import { valuesOf } from "./values";

type Artifact = components["schemas"]["Artifact"];

type Emitted = components["schemas"]["EmittedPipeline"];
type Kind = "settled" | "measured" | "read" | "optional" | "open";
type Tab = "preview" | "kept" | "main" | "config";

/** **The pipeline file, direction A with the AI beside it** (#499; the design canvas's boards
 *  "A · Editor" and "C · With the AI").
 *
 *  An outline on the left — the file's sections, its steps with their state, and the counts of
 *  how the values were decided, which filter the file. The file in the middle, with real tabs
 *  (`main.nf` and `nextflow.config` compile on first open), folds, and each value's reason opened
 *  beneath its own lines with *Ask the AI* and *Change*; any selected text can be asked about.
 *  The AI panel on the right is the builder's own conversation, and folds away. The text stays
 *  the server's: the page only says where each line belongs (`fileLines`, `folds`). */
export function PipelineFile({
  steps,
  preview,
  draftId,
  kept,
  onChange,
  onAsk,
  onSay,
  focusStep = null,
  aside = null,
}: {
  steps: AnsweredStep[];
  preview: AuthoringPreview | null;
  draftId: string | null;
  /** Whether a kept `pipeline.yml` exists to show beside the preview. */
  kept: boolean;
  /** Open a step on the canvas, to change one of its values. */
  onChange?: (node: string) => void;
  /** Put words in the composer, to finish and send. */
  onAsk?: (text: string) => void;
  /** Send words to the conversation now (*Explain this*). */
  onSay?: (text: string) => void;
  /** A step to open the file on (*Show in pipeline file*). */
  focusStep?: string | null;
  /** The builder's conversation, drawn as the AI panel. */
  aside?: React.ReactNode;
}) {
  const tiers = useTiers();
  const [filter, setFilter] = useState<Kind | null>(null);
  const [picked, setPicked] = useState<{ step: string; setting: string } | null>(null);
  const [tab, setTab] = useState<Tab>("preview");
  const [compiled, setCompiled] = useState(false);
  const [panel, setPanel] = useState(true);
  const values = valuesOf(steps);
  const artifact = useQuery({
    queryKey: ["artifact", draftId],
    queryFn: () => get<Artifact>(`/pipeline/drafts/${draftId}/artifact`),
    enabled: kept && tab === "kept" && Boolean(draftId),
    retry: false,
  });
  const emitted = useQuery({
    queryKey: ["emitted", draftId, preview?.revision],
    queryFn: () => compile(draftId!),
    enabled: compiled && Boolean(draftId),
    retry: false,
  });
  const open = (which: Tab) => {
    setTab(which);
    if ((which === "main" || which === "config") && !compiled) setCompiled(true);
  };
  const ready = preview?.state === "ready" ? preview.text : null;
  const text = tab === "kept" ? artifact.data?.text ?? null : ready;
  const fileText = ready ?? "";
  const lines = fileText.split("\n");
  const refs = ready !== null ? fileLines(ready) : [];
  const stepLine = (id: string) => lines.findIndex((l) => l === `- id: ${id}`);
  const [target, setTarget] = useState<number | null>(null);
  const jump = (index: number) => { if (index >= 0) setTarget(index); };
  useEffect(() => {
    if (focusStep && ready !== null) jump(stepLine(focusStep));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a new step to show, once the text is there
  }, [focusStep, ready !== null]);
  const setting = (step: string, name: string) =>
    steps.find((s) => s.id === step)?.settings.find((x) => x.name === name) ?? null;
  const kindOf = (value: Answered): Kind => open_(value) ? "open" : optionalOpen(value) ? "optional"
    : value.tier === 3 && value.evidence === "measured" ? "measured"
      : value.tier === 3 && value.evidence === "read_by_ai" ? "read" : "settled";
  const decorate = (index: number, line: string): LineDecoration => {
    const ref = refs[index];
    const value = ref ? setting(ref.step, ref.setting) : null;
    if (filter && !(/^- id: /.test(line) || (value && kindOf(value) === filter))) return { hidden: true };
    if (!ref) return null;
    const mark = ref.head && value ? markOf(value, tiers) : null;
    return {
      selected: picked?.step === ref.step && picked.setting === ref.setting,
      onSelect: () => setPicked(picked?.step === ref.step && picked.setting === ref.setting
        ? null : { step: ref.step, setting: ref.setting }),
      mark: mark && (
        <span className="inline-block px-[7px] rounded-full font-ui text-[10.5px] font-semibold" style={MARK_STYLE[mark.tone]}>
          {mark.words}
        </span>
      ),
    };
  };
  // The reason opens beneath the picked value's last line.
  const lastOfPicked = picked ? refs.reduce((last, ref, i) =>
    ref && ref.step === picked.step && ref.setting === picked.setting ? i : last, -1) : -1;
  const below = (index: number) => index === lastOfPicked && picked ? (
    <Reason step={steps.find((s) => s.id === picked.step) ?? null} setting={setting(picked.step, picked.setting)}
            tiers={tiers} onChange={onChange} onAsk={onAsk} onClose={() => setPicked(null)} />
  ) : null;
  const counts = ([["settled", values.settled, "settled"], ["measured", values.measured, "measured"],
    ["read", values.read, "read by AI"], ["optional", values.optional, "optional"],
    ["open", values.open, values.open === 1 ? "needs you" : "need you"]] as const).filter(([, n]) => n > 0);

  const download = () => {
    if (text === null) return;
    const url = URL.createObjectURL(new Blob([text], { type: "application/yaml" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "pipeline.yml";
    link.click();
    URL.revokeObjectURL(url);
  };
  const tabs: Tab[] = ["preview", ...(kept ? ["kept" as Tab] : []), "main", "config"];
  const about = (from: number, to: number, quoted: string, how: "explain" | "ask") => {
    const words = `About ${from === to ? `line ${from}` : `lines ${from}–${to}`} of pipeline.yml:\n`
      + quoted.split("\n").map((l) => `> ${l}`).join("\n");
    if (how === "explain") onSay?.(`${words}\nExplain this.`);
    else onAsk?.(`${words}\n`);
  };

  return (
    <div className="pipeline-file min-h-0" data-testid="pipeline-file" data-aside={aside && panel ? "open" : "closed"}>
      <Outline text={ready} steps={steps} counts={counts} filter={filter} onFilter={setFilter}
               onJump={(key) => jump(lines.findIndex((l) => l.startsWith(`${key}:`)))}
               onStep={(id) => jump(stepLine(id))} />
      <section aria-label="pipeline.yml" className="min-w-0 min-h-0 flex flex-col" style={{ borderLeft: "1px solid var(--line)" }}>
        <div className="flex items-end gap-2 px-4 pt-2" style={{ borderBottom: "1px solid var(--line)" }}>
          <div role="tablist" aria-label="which file" className="flex gap-[2px] font-data text-[12.5px]">
            {tabs.map((which) => (
              <button key={which} type="button" role="tab" aria-selected={tab === which}
                      data-testid={`artifact-tab-${which}`} onClick={() => open(which)}
                      className={`px-[14px] py-[7px] -mb-px rounded-t-button border cursor-pointer focus-visible:shadow-[var(--ring)]
                                  ${tab === which ? "text-ink" : "text-ink-2 bg-transparent border-transparent"}`}
                      style={tab === which ? { background: "var(--surface)", borderColor: "var(--line)", borderBottomColor: "var(--surface)" } : undefined}>
                {TAB_WORDS[which]}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2 pb-[6px]">
            {filter && (
              <span className="text-[12.5px] text-ink-3">
                showing {counts.find(([k]) => k === filter)?.[2]} ·{" "}
                <button type="button" onClick={() => setFilter(null)}
                        className="bg-transparent border-0 p-0 text-now-ink underline cursor-pointer">show all</button>
              </span>
            )}
            {emitted.data && (tab === "main" || tab === "config") && (
              <Secondary onClick={() => void emitted.refetch()} disabled={emitted.isFetching}>
                {emitted.isFetching ? "Compiling…" : "Compile again"}
              </Secondary>
            )}
            <Secondary onClick={download} disabled={text === null}>Download pipeline.yml</Secondary>
            {aside && (
              <Secondary onClick={() => setPanel(!panel)}>{panel ? "Hide the AI panel" : "Show the AI panel"}</Secondary>
            )}
          </div>
        </div>
        {emitted.error && <p role="alert" className="mx-5 mt-2 mb-0 text-[12.5px] text-needs-you-ink">{emitted.error.message}</p>}
        <div className="flex-1 min-h-0 overflow-auto py-3" style={{ background: "var(--surface)" }}>
          {tab === "kept" && kept ? <div className="px-5"><ArtifactView draftId={draftId} /></div>
            : tab === "main" || tab === "config"
              ? emitted.data ? <div className="px-5"><Code text={tab === "main" ? emitted.data.main_nf : emitted.data.nextflow_config} /></div>
                : emitted.error ? null : <p className="m-0 px-5 text-[12.5px] text-ink-3">Compiling…</p>
              : ready !== null ? (
                <>
                  <p className="m-0 mb-2 px-5 text-label text-ink-3" data-testid="preview-label">
                    Preview · revision {preview!.revision} · not kept · select any text to ask about it
                  </p>
                  <FileView text={fileText} decorate={decorate} below={below} onAbout={about} scrollTo={target} />
                </>
              ) : <div className="px-5"><ArtifactPreview preview={preview} /></div>}
        </div>
      </section>
      {aside && panel && (
        <section aria-label="Ask about this pipeline" className="file-aside min-h-0 flex flex-col"
                 style={{ borderLeft: "1px solid var(--line)" }}>
          <p className="m-0 px-4 py-[10px] text-[12.5px] text-ink-2" style={{ borderBottom: "1px solid var(--line)" }}>
            <span className="text-ink font-semibold">Ask about this pipeline</span> · the same conversation as the builder
          </p>
          <div className="flex-1 min-h-0 flex flex-col">{aside}</div>
        </section>
      )}
    </div>
  );
}

/** Ask for the draft's Nextflow; a refusal says why (MI0219), never an empty file. */
async function compile(draftId: string): Promise<Emitted> {
  const r = await fetch(`/api/pipeline/drafts/${draftId}/emitted`);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error((body as { detail?: string } | null)?.detail ?? `could not compile (${r.status})`);
  return body as Emitted;
}

const TAB_WORDS: Record<Tab, string> = {
  preview: "pipeline.yml", kept: "as kept", main: "main.nf", config: "nextflow.config",
};

const COUNT_STYLE: Record<Kind, React.CSSProperties> = {
  settled: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  measured: { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  read: { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  optional: { borderColor: "var(--line)", color: "var(--ink-3)", background: "transparent" },
  open: { borderColor: "transparent", color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
};

function Code({ text }: { text: string }) {
  return <pre className="m-0 font-data text-[12px] leading-[1.75] text-ink-2 whitespace-pre">{text}</pre>;
}

/** **A value's reason, beneath its own lines** (#499): the value, how it was decided and why,
 *  then *Ask the AI* and *Change*. */
function Reason({ step, setting, tiers, onChange, onAsk, onClose }: {
  step: AnsweredStep | null; setting: Answered | null; tiers: ReturnType<typeof useTiers>;
  onChange?: (node: string) => void; onAsk?: (text: string) => void; onClose: () => void;
}) {
  const mark = setting ? markOf(setting, tiers) : null;
  if (!step || !setting || !mark) return null;
  return (
    <section aria-label="the reason" onClick={(e) => e.stopPropagation()}
             className="font-ui my-1 px-[14px] py-[10px] rounded-panel border flex flex-wrap items-start gap-3 whitespace-normal"
             style={{ borderColor: "var(--now-line)", background: "var(--paper)" }}>
      <span className="shrink-0 mt-[2px] px-[9px] py-[1px] rounded-full text-[11.5px] font-semibold" style={MARK_STYLE[mark.tone]}>
        {mark.words}
      </span>
      <div className="flex-1 min-w-[180px] flex flex-col gap-1">
        <p className="m-0 text-[13px] text-ink">
          <span className="font-data font-semibold">{setting.value ?? "null"}</span>
          {setting.reason ? `: ${setting.reason}` : ""}
        </p>
        <p className="m-0 font-data text-[11.5px] text-ink-3">
          {[`${step.process}.${setting.name}`, `tier ${setting.tier}`, ...(setting.premise ?? []), setting.axis_reason]
            .filter(Boolean).join(" · ")}
        </p>
      </div>
      <div className="flex gap-2 shrink-0">
        {onAsk && <Secondary onClick={() => onAsk(`About ${step.process} ${setting.name}: `)}>Ask the AI</Secondary>}
        {onChange && <Secondary onClick={() => onChange(step.id)}>Change</Secondary>}
        <button type="button" aria-label="Close the reason" onClick={onClose}
                className="w-[28px] h-[28px] p-0 border-0 bg-transparent text-ink-2 text-[18px] cursor-pointer">×</button>
      </div>
    </section>
  );
}

/** The file's sections, in the file's own order, as the outline names them. */
const SECTIONS: Record<string, string> = {
  intent: "Goal", facts: "Facts", registry: "Registry", decisions: "Decisions", gate: "Checks",
};

const DOT: Record<Kind, string> = {
  open: "var(--needs-you)", measured: "var(--measured)", read: "var(--measured)", optional: "var(--line-2)",
  settled: "var(--done)",
};

/** **The outline beside the file** (direction A): its sections and steps, each taking the file to
 *  itself, a step's dot in the colour of what it needs; the counts, which filter the file. */
function Outline({ text, steps, counts, filter, onFilter, onJump, onStep }: {
  text: string | null;
  steps: AnsweredStep[];
  counts: readonly (readonly [Kind, number, string])[];
  filter: Kind | null;
  onFilter: (kind: Kind | null) => void;
  onJump: (key: string) => void;
  onStep: (id: string) => void;
}) {
  const keys = (text ?? "").split("\n").map((line) => /^([a-z_]+):/.exec(line)?.[1]).filter((k): k is string => !!k);
  const row = "w-full flex items-baseline justify-between gap-2 px-2 py-[6px] rounded-control border-0 bg-transparent text-left " +
    "text-[13px] text-ink-2 cursor-pointer hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]";
  const state = (step: AnsweredStep): Kind => {
    const v = valuesOf([step]);
    return v.open ? "open" : v.measured ? "measured" : v.read ? "read" : "settled";
  };
  return (
    <nav aria-label="outline of the file" className="file-outline min-h-0 overflow-auto px-3 py-3 flex flex-col gap-[2px]">
      <p className="m-0 mb-1 px-2 text-label text-ink-3">Outline</p>
      {keys.filter((k) => k in SECTIONS && k !== "decisions" && k !== "gate").map((key) => (
        <button key={key} type="button" className={row} onClick={() => onJump(key)}>{SECTIONS[key]}</button>
      ))}
      {keys.includes("steps") && (
        <>
          <button type="button" className={`${row} text-ink`} onClick={() => onJump("steps")}>
            Steps <span className="text-ink-3">{steps.length}</span>
          </button>
          <div className="flex flex-col pl-3 font-data text-[12px]">
            {steps.map((step) => (
              <button key={step.id} type="button" aria-label={`step ${step.id}, ${KIND_WORDS[state(step)]}`}
                      onClick={() => onStep(step.id)} className={`${row} justify-start text-[12px]`}>
                <span aria-hidden className="w-[7px] h-[7px] rounded-full shrink-0 self-center" style={{ background: DOT[state(step)] }} />
                <span className="truncate">{step.id}</span>
              </button>
            ))}
          </div>
        </>
      )}
      {keys.filter((k) => k === "decisions" || k === "gate").map((key) => (
        <button key={key} type="button" className={row} onClick={() => onJump(key)}>{SECTIONS[key]}</button>
      ))}
      {counts.length > 0 && (
        <div role="group" aria-label="how the values were decided"
             className="mt-auto pt-3 flex flex-wrap gap-[6px]" style={{ borderTop: "1px solid var(--line)" }}>
          {counts.map(([kind, n, words]) => (
            <button key={kind} type="button" aria-pressed={filter === kind} onClick={() => onFilter(filter === kind ? null : kind)}
                    className="px-[10px] py-[3px] rounded-full border text-[12px] cursor-pointer focus-visible:shadow-[var(--ring)]"
                    style={{ ...COUNT_STYLE[kind], ...(filter === kind ? { boxShadow: "0 0 0 2px var(--now)" } : {}) }}>
              {n} {words}
            </button>
          ))}
        </div>
      )}
    </nav>
  );
}

const KIND_WORDS: Record<Kind, string> = {
  open: "needs you", measured: "measured", read: "read by AI", optional: "optional", settled: "settled",
};
