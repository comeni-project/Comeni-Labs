import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import type { AuthoringPreview } from "../../api/types";
import { ArtifactView } from "../ArtifactView";
import { open, optionalOpen, type Answered, type AnsweredStep } from "../useBuilder";
import { useTiers } from "../useTiers";
import { ArtifactPreview, type LineDecoration } from "./ArtifactPreview";
import { Primary, Secondary } from "./blocks/parts";
import { fileLines } from "./fileLines";
import { MARK_STYLE, markOf } from "./valueMarks";
import { valuesOf } from "./values";

type Artifact = components["schemas"]["Artifact"];

type Emitted = components["schemas"]["EmittedPipeline"];
type Kind = "settled" | "measured" | "read" | "optional" | "open";
type Tab = "preview" | "kept" | "main" | "config";

/** **The pipeline file, file first** (one builder plan 5, issue 394; the *Pipeline file* board).
 *
 * `pipeline.yml` is the pipeline, so the file takes the page: each setting's first line carries
 * a mark of how its value was decided, any line of a setting opens its reason beside the file,
 * the counts filter the file (hiding lines, never editing them), and *Compile it* shows the
 * Nextflow it compiles to. The text stays the server's; the page only says where each line
 * belongs (`fileLines`) and what the frame says about that value.
 */
export function PipelineFile({
  steps,
  preview,
  draftId,
  kept,
  onChange,
  onAsk,
}: {
  steps: AnsweredStep[];
  preview: AuthoringPreview | null;
  draftId: string | null;
  /** Whether a kept `pipeline.yml` exists to show beside the preview. */
  kept: boolean;
  /** Open a step in the builder, to change one of its values. */
  onChange?: (node: string) => void;
  /** Put words in the composer and return to the conversation. */
  onAsk?: (text: string) => void;
}) {
  const tiers = useTiers();
  const [filter, setFilter] = useState<Kind | null>(null);
  const [picked, setPicked] = useState<{ step: string; setting: string } | null>(null);
  const [tab, setTab] = useState<Tab>("preview");
  const [compiled, setCompiled] = useState(false);
  const column = useRef<HTMLDivElement>(null);
  // A section's first line, found by its text: the file is the server's, so its keys are read, not assumed.
  const jump = (key: string) => Array.from(column.current?.querySelectorAll<HTMLElement>("[data-n]") ?? [])
    .find((line) => line.textContent?.startsWith(`${key}:`))?.scrollIntoView?.({ block: "start", behavior: "smooth" });
  const values = valuesOf(steps);
  // The kept file is read the way `ArtifactView` reads it, so Download takes the same bytes.
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
  const text = tab === "kept" ? artifact.data?.text ?? null : preview?.state === "ready" ? preview.text : null;
  const refs = preview?.state === "ready" ? fileLines(preview.text) : [];
  const setting = (step: string, name: string) =>
    steps.find((s) => s.id === step)?.settings.find((x) => x.name === name) ?? null;
  const kindOf = (value: Answered): Kind => open(value) ? "open" : optionalOpen(value) ? "optional"
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
      onSelect: () => setPicked({ step: ref.step, setting: ref.setting }),
      mark: mark && (
        <span className="inline-block px-[7px] rounded-full font-ui text-[10.5px] font-semibold" style={MARK_STYLE[mark.tone]}>
          {mark.words}
        </span>
      ),
    };
  };
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
  const tabs: Tab[] = [...(["preview"] as Tab[]), ...(kept ? ["kept" as Tab] : []),
    ...(compiled && emitted.data ? ["main" as Tab, "config" as Tab] : [])];

  return (
    <div className="pipeline-file min-h-0 overflow-auto" data-testid="pipeline-file">
      <div className="flex flex-col min-w-0 min-h-0">
        <div className="flex flex-wrap items-center gap-2 px-5 pt-4 pb-3" style={{ borderBottom: "1px solid var(--line)" }}>
          <div role="group" aria-label="how the values were decided" className="flex flex-wrap items-center gap-[6px]">
            {counts.map(([kind, n, words]) => (
              <button key={kind} type="button" aria-pressed={filter === kind} onClick={() => setFilter(filter === kind ? null : kind)}
                      className="px-[10px] py-[3px] rounded-full border text-[12.5px] cursor-pointer focus-visible:shadow-[var(--ring)]"
                      style={{ ...COUNT_STYLE[kind], ...(filter === kind ? { boxShadow: "0 0 0 2px var(--now)" } : {}) }}>
                {n} {words}
              </button>
            ))}
            {filter && (
              <span className="text-[12.5px] text-ink-3">
                showing {counts.find(([k]) => k === filter)?.[2]} ·{" "}
                <button type="button" onClick={() => setFilter(null)}
                        className="bg-transparent border-0 p-0 text-now-ink underline cursor-pointer">show all</button>
              </span>
            )}
          </div>
          <button type="button" onClick={download} disabled={text === null}
                  className="ml-auto px-[14px] py-[7px] rounded-button border text-[13px] font-semibold text-ink bg-surface
                             cursor-pointer focus-visible:shadow-[var(--ring)] disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ borderColor: "var(--line-2)" }}>
            Download pipeline.yml
          </button>
        </div>
        <div className="px-5 pt-3">
          <Sections text={preview?.state === "ready" ? preview.text : null} steps={steps.length} onJump={jump} />
        </div>
        <section aria-label="pipeline.yml" className="flex-1 min-h-0 flex flex-col">
          <div className="flex items-center gap-3 mx-5 mt-3">
            <div role="tablist" aria-label="which file" className="flex gap-1 p-1 rounded-button" style={{ background: "var(--paper)" }}>
              {tabs.map((which) => (
                <button key={which} type="button" role="tab" aria-selected={tab === which}
                        data-testid={`artifact-tab-${which}`} onClick={() => setTab(which)}
                        className={`px-3 py-[5px] rounded-control border text-[13px] cursor-pointer focus-visible:shadow-[var(--ring)]
                                    ${tab === which ? "text-ink font-semibold" : "text-ink-2 bg-transparent border-transparent"}`}
                        style={tab === which ? { background: "var(--surface)", borderColor: "var(--line)" } : undefined}>
                  {TAB_WORDS[which]}
                </button>
              ))}
            </div>
            <Primary onClick={() => { setCompiled(true); void emitted.refetch(); }} disabled={!draftId || emitted.isFetching}>
              {emitted.isFetching ? "Compiling…" : "Compile it"}
            </Primary>
          </div>
          {emitted.error && <p role="alert" className="mx-5 mt-2 mb-0 text-[12.5px] text-needs-you-ink">{emitted.error.message}</p>}
          <div ref={column} className="flex-1 min-h-0 overflow-auto px-5 py-4">
            {tab === "kept" && kept ? <ArtifactView draftId={draftId} />
              : tab === "main" && emitted.data ? <Code text={emitted.data.main_nf} />
                : tab === "config" && emitted.data ? <Code text={emitted.data.nextflow_config} />
                  : <ArtifactPreview preview={preview} decorate={decorate} />}
          </div>
        </section>
      </div>
      <Reason step={picked ? steps.find((s) => s.id === picked.step) ?? null : null}
              setting={picked ? setting(picked.step, picked.setting) : null}
              tiers={tiers} onChange={onChange} onAsk={onAsk} />
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

/** **The reason beside the file** (option A): the value, how it was decided, why, and what to do. */
function Reason({ step, setting, tiers, onChange, onAsk }: {
  step: AnsweredStep | null; setting: Answered | null; tiers: ReturnType<typeof useTiers>;
  onChange?: (node: string) => void; onAsk?: (text: string) => void;
}) {
  const mark = setting ? markOf(setting, tiers) : null;
  return (
    <aside aria-label="the reason" className="file-column min-h-0 overflow-auto px-5 py-4"
           style={{ borderLeft: "1px solid var(--line)", background: "var(--surface)" }}>
      {!step || !setting || !mark ? (
        <p className="m-0 text-[13px] text-ink-2">Click a value in the file to see why it is what it is.</p>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-label text-ink-3">{step.process} · setting</p>
          <h2 className="m-0 font-data text-[15px] font-semibold text-ink">{setting.name}</h2>
          <p className="m-0 font-data text-[20px] font-semibold text-ink">{setting.value ?? "null"}</p>
          <span className="self-start px-[9px] py-[1px] rounded-full text-[12px] font-semibold" style={MARK_STYLE[mark.tone]}>
            {mark.words}
          </span>
          {setting.reason && <p className="m-0 text-[13px] leading-[1.55] text-ink-2">{setting.reason}</p>}
          {(setting.premise ?? []).length > 0 && (
            <p className="m-0 font-data text-[11.5px] text-ink-3">{setting.premise.join(" · ")}</p>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {onChange && <Secondary onClick={() => onChange(step.id)}>Change it</Secondary>}
            {onAsk && <Secondary onClick={() => onAsk(`About ${step.process} ${setting.name}: `)}>Ask about it in the chat</Secondary>}
          </div>
        </div>
      )}
    </aside>
  );
}

/** The pipeline file's top-level keys as the board's chips name them, in the file's own order. */
const SECTIONS: Record<string, string> = {
  intent: "Goal", facts: "Facts", registry: "Registry", steps: "Steps", decisions: "Decisions", gate: "Checks",
};

/** **The board's section chips**: one for each section the file actually has, which takes the
 *  file to it. */
function Sections({ text, steps, onJump }: { text: string | null; steps: number; onJump: (key: string) => void }) {
  const keys = (text ?? "").split("\n").map((line) => /^([a-z_]+):/.exec(line)?.[1]).filter((k): k is string => !!k && k in SECTIONS);
  const chip = "px-[12px] py-[5px] rounded-full border text-[13px] cursor-pointer focus-visible:shadow-[var(--ring)]";
  return (
    <nav aria-label="sections of the file" className="flex flex-wrap gap-[8px]">
      {keys.map((key) => (
        <button key={key} type="button" onClick={() => onJump(key)} className={`${chip} text-ink-2 bg-[var(--surface)]`}
                style={{ borderColor: "var(--line-2)" }}>
          {key === "steps" ? `Steps ${steps}` : SECTIONS[key]}
        </button>
      ))}
    </nav>
  );
}

