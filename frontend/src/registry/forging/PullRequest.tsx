import { Failed } from "../../ui/States";
import type { AdaptationView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

const primary = "self-start px-5 py-[10px] rounded-button bg-action text-on-action font-semibold shadow-raise";

function checks(pull: NonNullable<AdaptationView["pull_request"]>): string {
  if (pull.checks === "green") return "Registry CI is green.";
  const why = pull.says ? `: ${pull.says}` : "";
  return pull.checks === "red" ? `Registry CI failed${why}.` : `Waiting for registry CI${why}.`;
}

/** Publishing a green draft: two buttons, as the operator asked. Open pull request puts it on
 *  `comeni-registry`; Approve pull request merges it, only once CI is green. */
export function PullRequestPanel({ view, actions }: {
  view: AdaptationView;
  actions: ReturnType<typeof useForgeActions>;
}) {
  const pull = view.pull_request;
  const reviewing = view.phase === "in_review" && pull;
  return (
    <div className="flex flex-col gap-3 pt-4 border-t border-line-soft">
      <h3 className="m-0 text-[14px] font-semibold">Pull request</h3>
      {view.phase === "tested" && (view.publish_unavailable
        ? <p className="m-0 text-[13px] text-needs-you-ink">{view.publish_unavailable}</p>
        : (
          <button type="button" onClick={() => actions.publish.mutate()} disabled={actions.publish.isPending}
                  className={primary}>
            Open pull request
          </button>
        ))}
      {view.phase === "publishing" && (
        <p role="status" className="m-0 text-[13px] text-action">Running the registry's checks, then opening the pull request…</p>
      )}
      {pull && pull.state !== "closed" && (
        <a href={pull.url} className="text-[13px]">Pull request #{pull.number} on comeni-registry</a>
      )}
      {reviewing && (
        <>
          <p className={`m-0 text-[13px] ${pull.checks === "red" ? "text-needs-you-ink" : "text-ink-2"}`}>{checks(pull)}</p>
          <button type="button" onClick={() => actions.approve.mutate()}
                  disabled={pull.checks !== "green" || pull.merging || actions.approve.isPending}
                  className={`${primary} disabled:bg-surface-2 disabled:text-ink-3 disabled:shadow-none`}>
            {pull.merging ? "Merging…" : "Approve pull request"}
          </button>
        </>
      )}
      {view.phase === "merged" && (
        <p className="m-0 text-[13px] text-done-ink">Merged into comeni-registry. It reaches the builder with the next release.</p>
      )}
      {actions.publish.isError && <Failed error={actions.publish.error} padded={false} />}
      {actions.approve.isError && <Failed error={actions.approve.error} padded={false} />}
    </div>
  );
}
