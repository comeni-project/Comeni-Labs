/** The eight words the interface uses, defined where a person is looking at them.
 *
 * **This exists because the person who co-designed Mendel could not read its own interface.**
 * Every screen was written for somebody who had already read `ARCHITECTURE.md`; nothing in the
 * product defined *contract*, *role*, *type*, *measurement*, *drift*, *hole*, *band* or
 * *proposal*, and all eight appear on screen.
 *
 * **One sentence, and never one that uses the word.** *"A contract is a contract file"* is the
 * failure mode of every glossary written by somebody who already knows, and
 * `Glossary.test.tsx` refuses it literally.
 *
 * `docs/reference/glossary.md` is the long form and the two are held in step in **both
 * directions** — a word on screen with no entry, and an entry nothing renders, are both defects.
 * That pair is the diagnostics guard's shape and it is deliberate: only one of them catches rot.
 */
export type Entry = { what: string; more?: string };

export const TERMS: Record<string, Entry> = {
  contract: {
    what: "what a tool takes, what it gives, and how to call it — one declared file per tool",
    more: "It is a hand-written binding to a Nextflow module, and a build refuses to emit if the two disagree.",
  },
  type: {
    what: "a semantic name for a thing that flows between tools — `alignment.bam`, `genome.fasta`",
    more: "Not a file format: a sorted and an unsorted BAM are the same format and different types.",
  },
  role: {
    what: "the job a tool does in a pipeline — sorting a BAM, building an index, aligning reads",
    more: "A judgement about this registry rather than a fact about the tool, which is why its own documentation cannot answer it.",
  },
  measurement: {
    what: "something observed about the data that a rule may read — read length, strandedness",
    more: "Each declares whether a tool can produce it; most are stated by a person rather than measured.",
  },
  drift: {
    what: "the source says something the contract does not — it was true once and no longer is",
    more: "The only kind of work here that breaks something already working, which is why it is coral.",
  },
  hole: {
    what: "a field the forge could not derive from the tool, so a person has to decide it",
    more: "Drafting fills in what the module states as fact and opens a hole for every judgement.",
  },
  band: {
    what: "how much a piece of work costs if it waits — not how likely it is to matter",
    more: "Drift blocks, an open question holds somebody up, an undrafted tool is an opportunity.",
  },
  proposal: {
    what: "nothing declared fits, so somebody proposed a new one and a person decides",
    more: "Vocabularies are closed, so a new type or role arrives through review rather than by being typed.",
  },
};
