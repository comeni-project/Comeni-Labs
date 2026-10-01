import { useEffect, useRef } from "react";

import { Preferences } from "./Preferences";

/** Settings as an overlay over whatever page you are on (the overlay's design, 2026-10-01).
 *
 * **The address is the state**: `?settings=<section>` opens it, so a section can be linked and
 * closing leaves you exactly where you were. It is the run sheet's kind of dialog — a scrim, the
 * page's second paper, a hairline — and on a phone it becomes a full-height sheet.
 *
 * **Escape closes it unless something inside used that Escape first**: a row's ⓘ note closes on
 * Escape in the capture phase and marks the event, so one press closes one thing.
 */
export function SettingsOverlay({
  section, onSelect, onClose,
}: { section: string; onSelect: (key: string) => void; onClose: () => void }) {
  const dialog = useRef<HTMLElement>(null);

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const page = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.documentElement.style.overflow = page;
      before?.focus?.();
    };
  }, []);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50">
      <div
        data-testid="settings-scrim"
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-[var(--scrim)]"
      />
      <section
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        className="settle absolute inset-0 md:inset-auto md:left-1/2 md:top-[60px]
                   md:-translate-x-1/2 md:w-[960px] md:max-w-[calc(100vw-48px)]
                   md:h-[min(680px,calc(100dvh-96px))] flex flex-col outline-none
                   bg-[var(--paper-2)] md:border border-line-2 md:rounded-[3px] shadow-e3"
      >
        <header className="flex items-center gap-[16px] pl-[16px] md:pl-[24px] pr-[16px] md:pr-[20px] pt-[16px] md:pt-[18px] pb-[12px] md:pb-[16px] border-b border-line">
          <div className="flex flex-col gap-[5px]">
            <h2 id="settings-title" className="m-0 text-[19px] font-semibold tracking-[-.02em] text-ink">
              Settings
            </h2>
            <span className="hidden md:block font-data text-label text-ink-4">
              this installation · every change is saved as you make it
            </span>
          </div>
          <span className="hidden md:inline ml-auto font-data text-label text-ink-4">esc</span>
          <button
            type="button"
            aria-label="Close settings"
            onClick={onClose}
            className="ml-auto md:ml-0 w-[44px] h-[44px] md:w-[32px] md:h-[32px] inline-flex items-center
                       justify-center bg-transparent border border-line-2 rounded-[3px]
                       text-ink-2 hover:text-ink hover:border-ink-4 cursor-pointer"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="1.8" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>
        <Preferences section={section} onSelect={onSelect} />
      </section>
    </div>
  );
}
