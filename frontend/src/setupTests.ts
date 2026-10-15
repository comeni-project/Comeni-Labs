import "@testing-library/jest-dom";

/** Supply dimensions because happy-dom has no layout engine.
 * TanStack's virtualizer reads offsetWidth/offsetHeight and observes them on mount, replacing
 * initialRect. A zero-height viewport renders no rows, so list tests must also assert that
 * relevant rows appear before checking virtualization bounds (A67).
 */
if (typeof HTMLElement !== "undefined") {
  for (const [name, value] of [["offsetWidth", 1200], ["offsetHeight", 600]] as const) {
    Object.defineProperty(HTMLElement.prototype, name, { configurable: true, get: () => value });
  }
}
