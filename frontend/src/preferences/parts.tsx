import type { ReactNode } from "react";

/** Small pieces the settings overlay draws in more than one place (its design, 2026-10-01). */

export function Badge({
  children, tone = "", dashed = false, className = "",
}: { children: ReactNode; tone?: string; dashed?: boolean; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-[5px] font-data text-[9.5px] uppercase
                  tracking-[.12em] px-[7px] py-[3px] rounded-[2px] whitespace-nowrap border
                  ${dashed ? "border-dashed border-ink-4 text-ink-2" : tone || "text-ink-3 border-line-2"}
                  ${className}`}
    >
      {children}
    </span>
  );
}

export function LockIcon({ label }: { label?: string }) {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.2" role={label ? "img" : undefined} aria-label={label}
         aria-hidden={label ? undefined : true}>
      <rect x="5" y="11" width="14" height="10" rx="1" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}
