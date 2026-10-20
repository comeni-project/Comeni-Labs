import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import type { AuthoringPreview } from "../../api/types";
import { ArtifactView } from "../ArtifactView";
import { open, type Answered, type AnsweredStep } from "../useBuilder";
import { useTiers } from "../useTiers";
import { ArtifactPreview } from "./ArtifactPreview";
import { valuesOf } from "./values";

type Artifact = components["schemas"]["Artifact"];

/** **The pipeline file — every value and its reason** (the *Pipeline file* board).
 *
 * `pipeline.yml` is the pipeline, and every value in it carries why it has that value. Reading
 * YAML to learn which values were measured and which still need you was the page this replaced;
 * here the values are a table read from the same frame the canvas draws, beside the file itself,
 * which stays the server's text — the table explains the file, it never stands in for it.
 */
export function PipelineFile({
  steps,
  preview,
  draftId,
  kept,
}: {
  steps: AnsweredStep[];
  preview: AuthoringPreview | null;
  draftId: string | null;
  /** Whether a kept `pipeline.yml` exists to show beside the preview. */
  kept: boolean;
}) {
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [tab, setTab] = useState<"preview" | "kept">("preview");
  const values = valuesOf(steps);
  // The kept file is read the way `ArtifactView` reads it, so Download takes the same bytes.
  const artifact = useQuery({
    queryKey: ["artifact", draftId],
    queryFn: () => get<Artifact>(`/pipeline/drafts/${draftId}/artifact`),
    enabled: kept && tab === "kept" && Boolean(draftId),
    retry: false,
  });
  const text = tab === "kept" ? artifact.data?.text ?? null : preview?.state === "ready" ? preview.text : null;
  const shown = steps
    .map((step) => ({ step, settings: onlyOpen ? step.settings.filter(open) : step.settings }))
    .filter(({ settings }) => !onlyOpen || settings.length > 0);

  const download = () => {
    if (text === null) return;
    const url = URL.createObjectURL(new Blob([text], { type: "application/yaml" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "pipeline.yml";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="pipeline-file min-h-0 overflow-auto" data-testid="pipeline-file">
      <div className="flex flex-col gap-4 p-5 min-w-0">
        <section aria-label="how the values were decided" className="rounded-panel border px-5 py-4 flex flex-wrap items-center gap-4"
                 style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
          <div className="flex-1 min-w-[260px]">
            <h2 className="m-0 text-heading font-semibold text-ink">
              {values.total} {values.total === 1 ? "value" : "values"}, and how each was decided
            </h2>
            <Bar values={values} />
            <p className="m-0 mt-2 text-[13px] text-ink-2">
              {values.settled} settled by a rule, a convention or you ·{" "}
              <span className="text-measured-ink">{values.measured} measured from your files</span> ·{" "}
              {values.open > 0
                ? <span className="text-needs-you-ink">{values.open} {values.open === 1 ? "needs" : "need"} you</span>
                : <span>nothing needs you</span>}
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" aria-pressed={onlyOpen} onClick={() => setOnlyOpen(!onlyOpen)}
                    className={`px-[14px] py-[8px] rounded-button border text-[13px] font-semibold cursor-pointer
                                focus-visible:shadow-[var(--ring)] ${onlyOpen ? "text-now-ink" : "text-ink bg-surface"}`}
                    style={{ borderColor: onlyOpen ? "var(--now-line)" : "var(--line-2)",
                             background: onlyOpen ? "var(--now-soft)" : undefined }}>
              Show only open
            </button>
            <button type="button" onClick={download} disabled={text === null}
                    className="px-[14px] py-[8px] rounded-button border text-[13px] font-semibold text-ink bg-surface
                               cursor-pointer focus-visible:shadow-[var(--ring)] disabled:opacity-40 disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--line-2)" }}>
              Download pipeline.yml
            </button>
          </div>
        </section>
        {onlyOpen && shown.length === 0 && <p className="m-0 text-[13px] text-ink-2">Nothing is open.</p>}
        {shown.map(({ step, settings }) => <StepValues key={step.id} step={step} settings={settings} />)}
      </div>

      <section aria-label="pipeline.yml" className="file-column min-h-0 flex flex-col"
               style={{ borderLeft: "1px solid var(--line)", background: "var(--surface)" }}>
        <div role="tablist" aria-label="which pipeline.yml" className="flex gap-1 m-4 p-1 rounded-button self-start"
             style={{ background: "var(--paper)" }}>
          {(["preview", "kept"] as const).map((which) => (
            <button key={which} type="button" role="tab" aria-selected={tab === which}
                    data-testid={`artifact-tab-${which}`} disabled={which === "kept" && !kept}
                    onClick={() => setTab(which)}
                    className={`px-3 py-[5px] rounded-control border text-[13px] cursor-pointer
                                disabled:opacity-40 disabled:cursor-not-allowed focus-visible:shadow-[var(--ring)]
                                ${tab === which ? "text-ink font-semibold" : "text-ink-2 bg-transparent border-transparent"}`}
                    style={tab === which ? { background: "var(--surface)", borderColor: "var(--line)" } : undefined}>
              {which === "preview" ? "as it would read" : "as kept"}
            </button>
          ))}
        </div>
        <div className="flex-1 min-h-0 overflow-auto px-4 pb-4">
          {tab === "kept" && kept ? <ArtifactView draftId={draftId} /> : <ArtifactPreview preview={preview} />}
        </div>
      </section>
    </div>
  );
}

/** The bar on the board: settled, measured and open, in proportion. Settled spends no colour. */
function Bar({ values }: { values: ReturnType<typeof valuesOf> }) {
  if (values.total === 0) return null;
  const part = (n: number) => `${(n / values.total) * 100}%`;
  return (
    <div aria-hidden className="mt-3 flex gap-[3px] h-[8px]">
      {values.settled > 0 && <span className="rounded-full" style={{ width: part(values.settled), background: "var(--line-2)" }} />}
      {values.measured > 0 && <span className="rounded-full" style={{ width: part(values.measured), background: "var(--measured)" }} />}
      {values.open > 0 && <span className="rounded-full" style={{ width: part(values.open), background: "var(--needs-you)" }} />}
    </div>
  );
}

function StepValues({ step, settings }: { step: AnsweredStep; settings: Answered[] }) {
  const tiers = useTiers();
  const counted = valuesOf([{ ...step, settings: step.settings }]);
  const counts = [
    counted.settled && `${counted.settled} settled`,
    counted.measured && `${counted.measured} measured`,
    counted.open && `${counted.open} open`,
  ].filter(Boolean).join(" · ");

  return (
    <section aria-label={step.process} className="rounded-panel border overflow-hidden"
             style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
      <header className="flex flex-wrap items-baseline gap-3 px-5 py-3" style={{ borderBottom: "1px solid var(--line)" }}>
        <h3 className="m-0 font-data text-[13.5px] font-semibold text-ink">{step.process}</h3>
        <span className="font-data text-[11.5px] text-ink-3 truncate min-w-0">{step.contract_id}</span>
        <span className="ml-auto text-[12.5px] text-ink-2">{counts}</span>
      </header>
      {step.settings.length === 0 ? (
        <p className="m-0 px-5 py-3 text-[13px] text-ink-3">Nothing to set — this step runs as its tool ships.</p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-label={`${step.process} settings`} className="w-full border-collapse text-left">
            <thead>
              <tr className="text-[12px] text-ink-3">
                <th className="font-normal px-5 py-2">Setting</th>
                <th className="font-normal px-3 py-2">Value</th>
                <th className="font-normal px-3 py-2">How it was decided</th>
                <th className="font-normal px-5 py-2">Why</th>
              </tr>
            </thead>
            <tbody>
              {settings.map((setting) => {
                const isOpen = open(setting);
                return (
                  <tr key={setting.name} aria-label={setting.name} style={{ borderTop: "1px solid var(--line-soft)" }}>
                    <td className="px-5 py-[10px] font-data text-[12.5px] text-ink align-top">{setting.name}</td>
                    <td className={`px-3 py-[10px] font-data text-[12.5px] align-top ${isOpen ? "text-needs-you-ink" : "text-ink"}`}>
                      {setting.value ?? "null"}
                    </td>
                    <td className="px-3 py-[10px] align-top">
                      <How setting={setting} open={isOpen} name={tiers.name(setting.tier)} />
                    </td>
                    <td className="px-5 py-[10px] text-[13px] text-ink-2 align-top">
                      {setting.reason}
                      {(setting.premise ?? []).length > 0 && (
                        <span className="block font-data text-[11.5px] text-ink-3 mt-1">{setting.premise.join(" · ")}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** How one value was decided, as a chip coloured by meaning: measured, open, or neither. */
function How({ setting, open: isOpen, name }: { setting: Answered; open: boolean; name: string }) {
  const [words, style] = isOpen
    ? ["needs you", { background: "var(--needs-you-soft)", color: "var(--needs-you-ink)" }]
    : setting.answered
      ? ["your answer", { background: "var(--now-soft)", color: "var(--now-ink)" }]
      : setting.tier === 3
        ? [name, { background: "var(--measured-soft)", color: "var(--measured-ink)" }]
        : [name, { border: "1px solid var(--line-2)", color: "var(--ink-2)" }];
  return (
    <span className="inline-block px-[8px] py-[1px] rounded-control text-[12px] font-semibold whitespace-nowrap"
          style={style}>
      {words}
    </span>
  );
}
