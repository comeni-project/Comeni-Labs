/** The pieces every block is built from: the ruled log's tick, a block frame, and two buttons.
 *
 * **One frame for everything a person can act on** — one border, one background, square — and
 * nothing for what they cannot. Prose on the log never gets a panel; the design record's reason
 * is that a refusal wearing the same border as a question reads as something you can answer.
 */

export type Tick = "you" | "resolver" | "model" | "person" | "open" | "wait" | "quiet";

export function TickMark({ kind }: { kind: Tick }) {
  const style: React.CSSProperties = {
    left: -20,
    top: 4,
    width: 7,
    height: 7,
    border: "1px solid var(--line-2)",
    background: "var(--paper)",
  };
  if (kind === "you") Object.assign(style, { background: "var(--link)", borderColor: "var(--link)" });
  if (kind === "model") Object.assign(style, { borderStyle: "dashed", borderColor: "var(--ink-2)" });
  if (kind === "person") Object.assign(style, { background: "var(--ink-2)", borderColor: "var(--ink-2)" });
  if (kind === "open") Object.assign(style, { borderColor: "var(--undecided)" });
  if (kind === "wait") Object.assign(style, { borderColor: "var(--measured)" });
  return <span aria-hidden data-tick={kind} className="absolute" style={style} />;
}

/** One entry on the log: a tick, then whatever the entry is. */
export function Turn({
  tick,
  children,
  anchor,
}: {
  tick: Tick;
  children: React.ReactNode;
  /** A node this entry is about — what selecting that node scrolls to. */
  anchor?: string;
}) {
  return (
    <li className="relative pb-[18px] list-none" data-decision-node={anchor}>
      <TickMark kind={tick} />
      {children}
    </li>
  );
}

export function BlockFrame({
  title,
  aside,
  children,
  actions,
  label,
}: {
  title: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  actions?: React.ReactNode;
  /** The accessible name of the region. */
  label: string;
}) {
  return (
    <section
      aria-label={label}
      className="border"
      style={{ borderColor: "var(--line-2)", background: "var(--paper-2)" }}
    >
      <header
        className="flex items-baseline justify-between gap-[10px] px-3 py-[9px]"
        style={{ borderBottom: "1px solid var(--line)" }}
      >
        <span className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3">{title}</span>
        {aside && <span className="font-data text-[9.5px] text-ink-3">{aside}</span>}
      </header>
      <div className="px-3 py-[11px]">{children}</div>
      {actions && (
        <footer
          className="flex items-center gap-2 px-3 py-[10px]"
          style={{ borderTop: "1px solid var(--line)" }}
        >
          {actions}
        </footer>
      )}
    </section>
  );
}

export function Primary(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="text-[12.5px] font-semibold px-[15px] py-[7px] border-0 cursor-pointer
                 bg-[var(--link)] text-paper disabled:opacity-40 disabled:cursor-not-allowed
                 focus-visible:shadow-[var(--ring)]"
    />
  );
}

export function Secondary(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="text-[12.5px] px-[13px] py-[7px] cursor-pointer bg-transparent text-ink-2
                 border border-[var(--surface-2)] hover:text-ink disabled:opacity-40
                 disabled:cursor-not-allowed focus-visible:shadow-[var(--ring)]"
    />
  );
}

/** Assistant prose — quieter than a person's, and never in a panel. */
export function Says({ children }: { children: React.ReactNode }) {
  return <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2">{children}</p>;
}
