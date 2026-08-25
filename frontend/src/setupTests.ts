import "@testing-library/jest-dom";

/** happy-dom has no layout engine: every element measures zero.
 *
 * Two components are virtualised — the Tasks tab and the console — and a virtualiser handed a
 * zero-height scroll element renders **no rows at all**. That does not fail loudly; it makes
 * every test about those lists pass by rendering nothing, which is the vacuous-guard failure
 * A67 names. `it renders fewer than 80 rows` is perfectly true of zero.
 *
 * **`offsetWidth`/`offsetHeight`, not `getBoundingClientRect`** — that is what
 * `@tanstack/virtual-core`'s `getRect` reads, and stubbing the other one leaves the window at
 * zero while looking fixed. `initialRect` alone is not enough either: `observeElementRect`
 * overwrites it with the element's real measurement on mount.
 */
for (const [name, value] of [["offsetWidth", 1200], ["offsetHeight", 600]] as const) {
  Object.defineProperty(HTMLElement.prototype, name, { configurable: true, get: () => value });
}
