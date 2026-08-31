import { Refusal } from "./Refusal";

/** Loading, empty and failed — three components, so no route invents its own.
 *
 * The empty state is CONTENT rather than an apology: it says what to do next.
 */
export function Loading({ what }: { what: string }) {
  return <p className="p-6 text-ink-3 text-body">Reading {what}…</p>;
}

export function Empty({ title, next }: { title: string; next?: string }) {
  return (
    <div className="p-6">
      <p className="text-body text-ink">{title}</p>
      {next && <p className="text-secondary text-ink-3 mt-1">{next}</p>}
    </div>
  );
}

/** What broke, in the words whatever broke it used.
 *
 * **It defers to `Refusal` when the message carries a code.** Two components rendered an error
 * and only one of them knew that `MD0512:` is a thing a person can look up — so the same
 * refusal read as a bare red sentence in one place and as an actionable one three files away.
 * One renderer, and the code keeps its `explain` line wherever it surfaces.
 *
 * **It never invents a cause.** There is no "something went wrong, please try again": the API's
 * refusals are coded precisely so they can be quoted, and a friendlier sentence would hide the
 * one string that says what to do.
 *
 * `padded` is off for an error shown *inside* a control's own row — a failed mutation belongs
 * under the button that failed, and 24px of padding there pushes it out of the step it explains.
 */
export function Failed({ error, padded = true }: { error: unknown; padded?: boolean }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className={padded ? "p-6" : ""}>
      {/^[A-Z]{2}\d{4}:/.test(message)
        ? <Refusal message={message} />
        : <p className="text-body text-fault m-0">{message}</p>}
    </div>
  );
}
