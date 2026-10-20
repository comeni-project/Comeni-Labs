import { useEffect, useState } from "react";

/** **What the canvas follows: whichever changed last** — the step the engine offers, or the step the
 *  person picked. A step on offer is there for most of a build, so letting it always win would mean
 *  a step picked from the step line never came into view. */
export function useFocus(ghost: string | null, selected: string | null): string | null {
  const [focus, setFocus] = useState(ghost ?? selected);
  useEffect(() => {
    if (ghost) setFocus(ghost);
  }, [ghost]);
  useEffect(() => {
    if (selected) setFocus(selected);
  }, [selected]);
  return focus;
}
