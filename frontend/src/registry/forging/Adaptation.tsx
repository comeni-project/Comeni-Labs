import { useState } from "react";
import { useParams } from "react-router";

import { useTitle } from "../../app/useTitle";
import { Failed, Loading } from "../../ui/States";
import { RegistryTabs } from "../RegistryTabs";
import { Chat } from "./Chat";
import { PieceItems, WriteItem } from "./PieceItems";
import { PullRequestPanel } from "./PullRequest";
import { TestsPanel } from "./Tests";
import { PIECES, useAdaptation, type AdaptationView } from "./useAdaptation";
import { useForgeActions, type AssemblyView } from "./useForgeActions";

const SETTLED = new Set(["approved", "removed"]);
const STANDS = new Set(["assembled", "testing", "tested", "publishing", "in_review", "merged"]);
const PUBLISHING = new Set(["tested", "publishing", "in_review", "merged"]);

/** `/registry/forging/:id` (boards 3–3g): the pieces in order, the current one's items, the
 *  chat, and assembling once everything is approved. */
export function Adaptation() {
  const id = useParams().id ?? "";
  const adaptation = useAdaptation(id);
  const actions = useForgeActions(id);
  const [chosen, setChosen] = useState<string | null>(null);
  const [about, setAbout] = useState<string | null>(null);
  const [writing, setWriting] = useState(false);
  const view = adaptation.data;
  useTitle(view ? `Forging ${view.path}` : "Forging");

  if (adaptation.isPending) return <><RegistryTabs /><Loading what="the adaptation" /></>;
  if (adaptation.isError || !view) return <><RegistryTabs /><Failed error={adaptation.error} /></>;

  const piece = chosen ?? view.next_piece ?? "tests";
  const items = view.items.filter((i) => i.piece === piece);
  const done = PIECES.filter((p) => {
    const its = view.items.filter((i) => i.piece === p);
    return its.length > 0 && its.every((i) => SETTLED.has(i.status));
  }).length;
  const busy = view.phase === "drafting" || view.phase === "asking";

  return (
    <div className="min-h-full bg-paper-2">
      <RegistryTabs />
      <div className="gutter pt-[18px] flex flex-wrap items-center gap-3">
        <h1 className="m-0 text-[22px] font-semibold">Forging <span className="font-data font-medium">{view.path}</span>{" "}
          <span className="font-data text-[15px] text-ink-3">{view.version}</span></h1>
        {view.depends_on.length > 0 && (
          <span className="text-[12.5px] text-measured-ink">uses pending vocabulary from {view.depends_on.length} assembled draft(s)</span>
        )}
        <span className="ml-auto text-[13px] text-ink-3">{done} of {PIECES.length} pieces approved</span>
      </div>
      <div className="gutter py-[18px] flex flex-wrap gap-5 items-start">
        <nav aria-label="Pieces" className="basis-full sm:basis-auto sm:flex-[0_1_230px] sm:min-w-[200px] bg-surface border border-line rounded-panel p-[10px] [contain:inline-size] sm:[contain:none]">
          {/* A row you scroll at phone width (board 3g), a list beside the piece above it. */}
          <ol className="list-none m-0 p-0 flex flex-row sm:flex-col gap-[2px] overflow-x-auto">
            {PIECES.map((p) => {
              const its = view.items.filter((i) => i.piece === p);
              const waiting = its.filter((i) => !SETTLED.has(i.status)).length;
              const note = its.length === 0 ? (p === view.next_piece ? "not started" : "not yet")
                : waiting ? `${waiting} waiting for you` : "approved";
              return (
                <li key={p} className="shrink-0">
                  <button type="button" onClick={() => { setChosen(p); setWriting(false); }}
                          aria-current={p === piece ? "step" : undefined}
                          className={`w-full text-left flex flex-col px-[10px] py-[9px] rounded-control border-0 ${
                            p === piece ? "bg-now-soft" : "bg-transparent"}`}>
                    <span className="font-medium capitalize">{p}</span>
                    <span className={`text-[12px] ${waiting ? "text-measured-ink" : "text-ink-3"}`}>{note}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <section aria-labelledby="piece" className="flex-[999_1_520px] min-w-0 bg-surface border border-line rounded-panel overflow-hidden">
          <div className="flex flex-wrap items-baseline gap-[10px] px-[22px] py-[18px] border-b border-line">
            <h2 id="piece" className="m-0 text-[17px] font-semibold capitalize">{view.ready ? "Assembly" : piece}</h2>
            {busy && <span role="status" className="text-[12.5px] text-action">The AI is drafting…</span>}
          </div>
          {view.ready ? (
            <Assembly view={view} actions={actions} />
          ) : (
            <>
              {items.length === 0 && !writing && piece === view.next_piece && (
                <Start piece={piece} busy={busy} onDraft={() => actions.draft.mutate(piece)}
                       onWrite={() => setWriting(true)} />
              )}
              {actions.draft.isError && <div className="px-[22px] py-3"><Failed error={actions.draft.error} padded={false} /></div>}
              <PieceItems items={items} actions={actions}
                          onReject={(key) => setAbout(key)} />
              {(writing || items.length > 0) && piece === view.next_piece && (
                <details className="border-t border-line-soft" open={writing}>
                  <summary className="px-[22px] py-3 cursor-pointer text-[13px] text-ink-2">Write an item yourself</summary>
                  <WriteItem piece={piece} items={view.items} actions={actions} />
                </details>
              )}
            </>
          )}
        </section>

        <Chat view={view} actions={actions} about={about} setAbout={setAbout} />
      </div>
    </div>
  );
}

function Start({ piece, busy, onDraft, onWrite }: {
  piece: string; busy: boolean; onDraft: () => void; onWrite: () => void;
}) {
  return (
    <div className="px-[22px] py-7 flex flex-col gap-4">
      <p className="m-0 text-ink-2 leading-[1.55]">How do you want to write the {piece}?</p>
      <div className="flex flex-wrap gap-[14px]">
        <div className="flex-[1_1_260px] border border-line-2 rounded-panel p-[18px] flex flex-col gap-[10px]">
          <span className="font-semibold">Draft with the AI</span>
          <span className="text-[13px] text-ink-2">The AI reads the module's files and proposes each item. Nothing counts until you approve it.</span>
          <button type="button" disabled={busy} onClick={onDraft}
                  className="self-start px-5 py-[10px] rounded-button bg-action text-on-action font-semibold shadow-raise">
            Draft with the AI
          </button>
        </div>
        <div className="flex-[1_1_260px] border border-line-2 rounded-panel p-[18px] flex flex-col gap-[10px]">
          <span className="font-semibold">Write it myself</span>
          <span className="text-[13px] text-ink-2">Your entries count as your decisions; the same checks run on them.</span>
          <button type="button" onClick={onWrite}
                  className="self-start px-5 py-[10px] rounded-button border border-line-2 bg-surface font-medium">
            Write it myself
          </button>
        </div>
      </div>
    </div>
  );
}

function Assembly({ view, actions }: { view: AdaptationView; actions: ReturnType<typeof useForgeActions> }) {
  const result: AssemblyView | undefined = actions.assemble.data;
  return (
    <div className="px-[22px] py-5 flex flex-col gap-4">
      <p className="m-0 text-ink-2">
        {STANDS.has(view.phase) && !result
          ? "Assembled: the draft loads over the registry and conforms."
          : "Every piece is approved. Assembling writes the registry files into a draft layer and checks them with the builder's own code. Nothing goes into the registry until a pull request is merged."}
      </p>
      {!STANDS.has(view.phase) && (
        <button type="button" onClick={() => actions.assemble.mutate()} disabled={actions.assemble.isPending}
                className="self-start px-5 py-[10px] rounded-button bg-action text-on-action font-semibold shadow-raise">
          Assemble
        </button>
      )}
      {actions.assemble.isError && <Failed error={actions.assemble.error} padded={false} />}
      {result && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-[10px]">
            <span className={`px-3 py-2 rounded-control border text-[13.5px] ${result.loaded ? "border-done text-done-ink" : "border-needs-you text-needs-you-ink"}`}>
              {result.loaded ? "✓ Loads over the registry" : "✕ Does not load"}
            </span>
            <span className={`px-3 py-2 rounded-control border text-[13.5px] ${result.conforms ? "border-done text-done-ink" : "border-needs-you text-needs-you-ink"}`}>
              {result.conforms ? "✓ Contract conforms to main.nf" : "✕ Does not conform"}
            </span>
          </div>
          {result.problems.map((p, n) => (
            <p key={n} className="m-0 text-[13px] text-needs-you-ink"><span className="font-data">{p.code}</span> {p.says}</p>
          ))}
          {result.blames && <p className="m-0 text-[13px]">The {result.blames} re-opened.</p>}
          {result.files.length > 0 && (
            <ul className="m-0 p-0 list-none border border-line rounded-control">
              {result.files.filter((f) => !f.includes("/module/")).map((f) => (
                <li key={f} className="px-3 py-2 border-b border-line-soft font-data text-[13px]">{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {STANDS.has(view.phase) && <TestsPanel view={view} actions={actions} />}
      {PUBLISHING.has(view.phase) && <PullRequestPanel view={view} actions={actions} />}
    </div>
  );
}
