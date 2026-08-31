/** *Run this* — the one control that crosses from Mendel to Wiener.
 *
 * `docs/design/wiener.md` §12: *"The user sees one button."* They see two, and the second one
 * is not a step somebody forgot to hide — **uploading is what discovers the parameters**. The
 * artifact declares its own holes (`params { input = null }`) and Wiener reads them out on
 * upload, so the form cannot exist before the upload has happened. Asking for a samplesheet
 * before knowing whether this pipeline wants one would be the interface guessing.
 *
 * **A gate is what unlocks it, and the reason is on the button rather than in this file.**
 * `execution-boundary.md` §3 keeps *gate* and *run* apart; nothing about that changes here.
 * What changes is that a pipeline which has proved itself can now go somewhere.
 */
import { useNavigate } from "react-router";

import { TokenPrompt } from "../wiener/Token";
import { useSubmit } from "./useSubmit";

/** **The run sheet's primary, in `--link` and not `--pea`.** `_run_sheet.html` ends on one blue
 *  `Start run`; green is this product's *settled / passed* colour and a green primary here reads
 *  as a verdict rather than an action. The label stays `Send to Wiener` because that is what the
 *  click does — the browser is the courier and neither API learns the other exists — and calling
 *  it `Start run` would hide the second click that `docs/design/wiener.md` §12 says is the point:
 *  uploading is what discovers the parameters. */
const button =
  "px-[24px] py-[9px] text-[13.5px] font-semibold bg-[var(--link)] text-paper border-0 " +
  "cursor-pointer lift disabled:opacity-40 disabled:cursor-not-allowed";

export function SubmitPanel({
  draftId,
  gated,
}: {
  draftId: string | null;
  gated: boolean;
}) {
  const submit = useSubmit(draftId);
  const navigate = useNavigate();

  if (submit.runId) {
    // Navigation happens on a click rather than automatically: a run that steals the page the
    // instant it is accepted takes the pipeline away from somebody who was still reading it.
    return (
      <div className="p-3 flex flex-col gap-2">
        <span className="text-body">
          Accepted as <code className="font-data">{submit.runId.slice(0, 8)}</code>.
        </span>
        <button
          data-testid="go-to-run"
          className={button + " self-start"}
          onClick={() => navigate(`/runs/${submit.runId}`)}
        >
          Watch it
        </button>
      </div>
    );
  }

  if (submit.unauthorized) {
    // Retrying on save rather than telling somebody to press the button again: they already
    // pressed it, and the only thing that was missing is now supplied.
    return <TokenPrompt onSaved={() => submit.send()} />;
  }

  const stopped = !draftId
    ? "Keep this pipeline first."
    : !gated
      ? "Gate it first — a run costs real time on real data, and a gate is what proves the file works."
      : null;

  return (
    <div className="p-3 flex flex-col gap-3">
      {submit.artifact === null ? (
        <div className="flex items-center gap-2">
          <button
            data-testid="send-to-wiener"
            className={button}
            disabled={stopped !== null || submit.sending}
            title={stopped ?? "Copy this pipeline into Wiener's own store"}
            onClick={() => submit.send()}
          >
            {submit.sending ? "Sending…" : "Send to Wiener"}
          </button>
          {stopped && <span className="text-secondary text-ink-3">{stopped}</span>}
        </div>
      ) : (
        <>
          <p className="text-secondary text-ink-3">
            Stored as <code className="font-data">{submit.artifact.artifact_id.slice(0, 8)}</code>
            , {(submit.artifact.size_bytes / 1024).toFixed(0)} kB. Wiener owns it from here.
          </p>
          {submit.artifact.declared.length === 0 ? (
            <p className="text-secondary text-ink-3">
              This pipeline asks for nothing — every value it needs is already in the artifact.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              <p className="text-secondary text-ink-3">
                These are the values Mendel could not justify, so it left them null. They are
                yours, they are not stored, and they never reach Mendel.
              </p>
              {submit.artifact.declared.map((name) => (
                <label key={name} className="flex items-center gap-2">
                  <span className="font-data text-body w-28 text-ink-3">{name}</span>
                  <input
                    data-testid={`param-${name}`}
                    value={submit.values[name] ?? ""}
                    onChange={(event) => submit.set(name, event.target.value)}
                    placeholder="a path on the machine that runs this"
                    className="flex-1 px-2 py-1 rounded-r bg-surface border border-line
                               font-data text-body text-ink"
                  />
                </label>
              ))}
            </div>
          )}
          <button
            data-testid="start-run"
            className={button + " self-start"}
            disabled={submit.unfilled.length > 0 || submit.starting}
            title={
              submit.unfilled.length
                ? `Still empty: ${submit.unfilled.join(", ")}`
                : "Submit the run"
            }
            onClick={() => submit.start()}
          >
            {submit.starting ? "Starting…" : "Start run"}
          </button>
        </>
      )}
      {submit.error && (
        <p data-testid="submit-error" className="text-secondary text-[var(--undecided)]">
          {submit.error}
        </p>
      )}
    </div>
  );
}
