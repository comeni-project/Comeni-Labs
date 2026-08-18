import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { useKeys } from "../app/useKeys";

/** `J`/`K` to move, Enter to open — `forge-review.md` §4.
 *
 * `A` and `E` are in the design's map and are NOT here: they act on the answer screen, which
 * is phase 2. Half a keyboard map is the right amount when half of what it drives exists.
 *
 * Separate from `useKeys` because the key map is one concern and which row is selected is
 * another; the queue is not the last list that will want this.
 */
export function useRowKeys(subjects: string[]) {
  const [index, setIndex] = useState(0);
  const navigate = useNavigate();

  // The list shrinks when a question is answered. An index past the end selects nothing and
  // sends Enter to `/forge/queue/question/undefined`.
  useEffect(() => {
    setIndex((i) => Math.min(i, Math.max(subjects.length - 1, 0)));
  }, [subjects.length]);

  // `subjects` is a fresh array every render — the caller builds it with `.map()` — so the
  // memo is keyed on its CONTENT, not its identity. Keyed on the array it would recompute
  // every render and `useKeys` would tear down and re-add its window listener each time.
  //
  // Closing over `subjects` is still safe: if the content changed, `key` changed and the memo
  // rebuilt with the new array; if it did not, the array it holds is equal to the current one.
  const key = subjects.join(" ");

  const map = useMemo(
    () => ({
      // Clamped rather than wrapped: in a work queue, wrapping returns you to rows you have
      // already read and you do not notice for several presses.
      j: () => setIndex((i) => Math.min(i + 1, subjects.length - 1)),
      k: () => setIndex((i) => Math.max(i - 1, 0)),
      enter: () => {
        const subject = subjects[index];
        if (subject) navigate(`/forge/queue/question/${encodeURIComponent(subject)}`);
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` stands in for `subjects`
    [key, index, navigate],
  );

  useKeys(map);
  return { index };
}
