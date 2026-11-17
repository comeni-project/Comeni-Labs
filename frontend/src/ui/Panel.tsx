import { useId, type ReactNode } from "react";

/** A titled section of a page: the board's card, with its title row and actions. */
export function Panel({ title, hint, actions, children, className = "" }: {
  title?: string;
  hint?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <section aria-labelledby={title ? id : undefined}
             className={`bg-surface border border-line rounded-panel min-w-0 ${className}`}>
      {title && (
        <header className="flex items-baseline gap-[10px] flex-wrap px-5 pt-4 pb-[10px]">
          <h2 id={id} className="m-0 text-[15.5px] font-semibold text-ink">{title}</h2>
          {hint && <span className="text-[12.5px] text-ink-3">{hint}</span>}
          {actions && <span className="ml-auto flex items-center gap-2">{actions}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
