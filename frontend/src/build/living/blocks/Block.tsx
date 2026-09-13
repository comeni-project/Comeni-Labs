import type { AuthoringBlock } from "../../../api/types";
import { processName } from "../format";
import { BlockFrame, Primary, Says, Secondary } from "./parts";

/** Every block kind the server can send, rendered — **an exhaustive switch**.
 *
 * A ninth kind added on the server fails `tsc` here until it has a renderer, which is the intended
 * order: a block the page cannot draw would otherwise render as nothing, and a turn with nothing in
 * it reads as the model having said nothing.
 */
export function Block({
  block,
  actions,
}: {
  block: AuthoringBlock;
  /** Controls for a block that is waiting on a person. Absent once it has been answered. */
  actions?: React.ReactNode;
}) {
  switch (block.kind) {
    case "narrative":
      return <Says>{block.text}</Says>;

    case "goal_summary":
      return (
        <BlockFrame label="the goal as understood" title="Your goal" actions={actions}>
          <dl className="m-0 grid grid-cols-[48px_1fr] gap-x-3 gap-y-[6px] text-[12.5px] leading-[1.55]">
            <dt className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3 pt-[3px]">have</dt>
            <dd className="m-0 text-ink">{block.have}</dd>
            <dt className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3 pt-[3px]">do</dt>
            <dd className="m-0 text-ink">{block.do}</dd>
            <dt className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3 pt-[3px]">get</dt>
            <dd className="m-0 text-ink">{block.get}</dd>
          </dl>
        </BlockFrame>
      );

    case "question":
      return (
        <BlockFrame
          label={block.asks}
          title="A question"
          aside={block.exhaustive ? "every option" : "the likely options"}
          actions={actions}
        >
          <p className="m-0 mb-2 text-[13px] text-ink">{block.asks}</p>
          <p className="m-0 mb-3 text-[12px] text-ink-3">{block.why_open}</p>
          <ul className="m-0 p-0">
            {block.options.map((option) => (
              <li key={option.id} className="list-none mb-[6px] px-[10px] py-2 border"
                  style={{ borderColor: "var(--line)" }}>
                <span className="text-[12.5px] text-ink">{option.label}</span>
                {option.recommended && <span className="ml-2 font-data text-[9.5px] text-link">recommended</span>}
              </li>
            ))}
          </ul>
        </BlockFrame>
      );

    case "step_proposal":
      // The interactive card is `StepProposalCard`; this is its read-only form in history.
      return (
        <Says>
          {processName(block.node)} — {block.reason}
        </Says>
      );

    case "setting_request":
      return (
        <BlockFrame label={`a value for ${block.setting}`} title={`${processName(block.node)} · ${block.setting}`}
                    aside={block.current ? `now ${block.current}` : "not set"} actions={actions}>
          <p className="m-0 mb-2 text-[12.5px] text-ink">{block.reason}</p>
          {block.premise && <p className="m-0 text-[11.5px] text-ink-3">{block.premise}</p>}
        </BlockFrame>
      );

    case "change_set":
      return (
        <BlockFrame label="the change this would make" title="This would change" actions={actions}>
          <p className="m-0 mb-2 text-[12.5px] text-ink">{block.summary}</p>
          <ul className="m-0 p-0 font-data text-[11px]">
            {block.removes.map((node) => (
              <li key={`-${node}`} className="list-none text-[var(--undecided)]">− {processName(node)}</li>
            ))}
            {block.adds.map((node) => (
              <li key={`+${node}`} className="list-none text-ink">+ {processName(node)}</li>
            ))}
            {block.settings.map((setting) => (
              <li key={`~${setting}`} className="list-none text-ink-2">~ {setting}</li>
            ))}
          </ul>
        </BlockFrame>
      );

    case "receipt":
      return (
        <p className="m-0 font-data text-[10px] leading-[1.5] text-ink-4">
          {block.summary} · revision {block.revision}
        </p>
      );

    case "notice":
      return <NoticeLine notice={block.notice} text={block.text} code={block.code ?? null} actions={actions} />;
  }
}

const NOTICE_TITLE: Record<string, string> = {
  pending: "Working on it",
  refusal: "It would not answer",
  stale: "This answer is out of date",
  validation: "Something to check",
  complete: "Done",
};

/** A notice is a sentence with a title and a code, and never a panel. */
export function NoticeLine({
  notice,
  text,
  code,
  actions,
}: {
  notice: string;
  text: string;
  code: string | null;
  actions?: React.ReactNode;
}) {
  return (
    <div role={notice === "refusal" ? "alert" : "status"}>
      <p className="m-0 text-[13px] text-ink">
        <span aria-hidden className="mr-2 text-[10px]"
              style={{ color: notice === "refusal" ? "var(--undecided)" : notice === "stale" ? "var(--measured)" : "var(--ink-3)" }}>
          {notice === "refusal" ? "●" : "○"}
        </span>
        {NOTICE_TITLE[notice] ?? notice}
      </p>
      <p className="m-0 mt-1 text-[12.5px] leading-[1.6] text-ink-2">
        {text}
        {code && <span className="ml-2 font-data text-[10px] text-ink-3">{code}</span>}
      </p>
      {actions && <div className="flex gap-2 mt-3">{actions}</div>}
    </div>
  );
}

export { Primary, Secondary };
