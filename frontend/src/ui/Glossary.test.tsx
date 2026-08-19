import { describe, expect, it } from "vitest";

import { TERMS } from "./glossary";

/** The eight words the interface uses without defining them.
 *
 * **Both directions, like the diagnostics guard.** A word on screen with no entry is a word a
 * person cannot look up; an entry nothing renders is documentation for a screen that no longer
 * says it. `docs/reference/diagnostics.md` has had exactly this pair of tests since Plan 1,
 * because only one of them catches rot.
 */
const IN_THE_DOC = [
  "contract",
  "type",
  "role",
  "measurement",
  "drift",
  "hole",
  "band",
  "proposal",
];

describe("the glossary", () => {
  it("defines every word the interface uses", () => {
    for (const term of IN_THE_DOC) {
      expect(TERMS[term], `\`${term}\` is in docs/reference/glossary.md with no entry here`)
        .toBeTruthy();
    }
  });

  it("has no entry nothing uses", () => {
    // An entry for a word no screen says is documentation for something that moved. The
    // diagnostics guard calls this declared-but-never-emitted and treats it as a defect.
    expect(Object.keys(TERMS).sort()).toEqual([...IN_THE_DOC].sort());
  });

  it("says what each word means in one sentence a person can read", () => {
    for (const [term, entry] of Object.entries(TERMS)) {
      expect(entry.what.length, `${term} has no definition`).toBeGreaterThan(20);
      // **Not a definition that uses the word.** "A contract is a contract file" is the failure
      // mode of every glossary written by somebody who already knows.
      expect(entry.what.toLowerCase().startsWith(term)).toBe(false);
    }
  });
});
