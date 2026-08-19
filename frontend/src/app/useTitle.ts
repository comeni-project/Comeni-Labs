import { useEffect } from "react";

const SITE = "Mendel · Comeni Labs";

/** What the browser tab says.
 *
 * **Every tab said `frontend`** — Vite's scaffold default, shipped through the whole of 3A and
 * 3B. A person with three tabs open could not tell which was the queue.
 *
 * Screen first, product last: a tab strip truncates from the right, so the half that survives
 * has to be the half that distinguishes one tab from another.
 */
export function useTitle(what?: string) {
  useEffect(() => {
    document.title = what ? `${what} · ${SITE}` : SITE;
    return () => {
      document.title = SITE;
    };
  }, [what]);
}
