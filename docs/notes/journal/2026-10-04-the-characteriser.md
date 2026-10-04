# 2026-10-04 — the characteriser (14.7.7), built in five parts

## Where things stand

- **A sample nothing here reads is read by the AI**, at protection level 0. Up to 8 KB of its
  text (gzip recognised by its first bytes, the first stretch of readable text) goes through
  door 6 on the AI worker. The model chooses a family, then a type, from the closed vocabulary,
  and may name only the declared states and measurements a line of the file states, **quoting
  that line**. The engine checks each quote: within one line, at least 8 characters. What
  passes is recorded as *read by AI* at tier 3; a type an inspector reads is handed back and
  measured. Walked live with `gemma3:12b`:
  - a FASTA is read as `genome.fasta` and answers the genome question;
  - a BAM is read as `alignment.bam` and `coordinate_sorted`, quoting `@HD VN:1.6 SO:coordinate`;
  - a FASTQ named `.txt` is handed back, re-sent by the browser, and measured;
  - random bytes send nothing.

  Readings take 10–20 s; a hand-back 33–54 s.
- **Guards:**
  - `uv run pytest tests/guards/test_egress.py`: door 6; `SAMPLE_FIELDS`; only door 6 reaches
    `Mark.SAMPLE`; the excerpt bounded by its type. Watched failing, in the guard ledger.
  - `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_characterise_excerpt.py
    packages/mendel-api/tests/test_characterise_reading.py
    packages/mendel-api/tests/test_authoring_characterise.py`.
- `make check`: 3431 passed. The frontend: 658 passed, 1 skipped.

## What changed

- **Spec** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md`, with §14 (evidence)
  added after the walk. **Plans** `2026-10-04-characteriser-1` to `-5`, each ticked with an
  execution record.
- **1, the declarations:**
  - commits 1b0376ec, acec32a6, a07c6978, 9289c9ba, 8f2b116b;
  - review fixes c4dc07d7 (#237).
- **2, the excerpt and the job:**
  - commits bd3efdb3, 33503329, 4167bbd9, f179d17f, a7d1ca55, 5db75701;
  - review fixes cc2a9d55 (#241).
- **3, the card:**
  - commits 0d51f2aa, 1f4d3843, 427a0e45, 44b3428c, 9509aab0;
  - the canvas *Uploading a sample* gained a page, *Read by AI* (12 artboards).
- **5, evidence:**
  - commits b880faa0, d574bcc0;
  - walk fixes 02c87a45 (#243) and #245;
  - review fixes 97bc0554 (#246).
- **4, the docs:** 8ac6d687 (invariants 3, 14, 15; the protocol page; the builder page).

## Decisions and why

- **The operator's brainstorm** (spec §2):
  - a decoded text excerpt, sent automatically at level 0;
  - the family step, then the type;
  - a type the engine reads is handed back to its inspector;
  - the registry's `describes:` decides which measurements a model may read;
  - the vocabulary stays closed, and a model's sightings are kept in `unmatched` for #236;
  - the call runs as a job on the AI worker.
- **Every property carries its evidence** (#244, the operator's idea). The value stays a closed
  id, the reason is free text, and the engine checks the reason. The alternatives were refusing
  the whole reply, which meant a local model never read a FASTA, or reading no states at all.
- **Rulings made executing**, each with what it costs if wrong (the plans' execution records
  hold them all):
  - door 6 carries only the excerpt, `binary_before` and the registry digest;
  - `SAMPLE_FIELDS` is counted apart from free text;
  - no `SCHEMA_VERSION` bump: a new enum value, not a field;
  - the upload is offered on every input question when the AI may read;
  - a hand-back's type is recorded as *measured*;
  - a stale reading reads as *no answer* after the job timeout plus a minute;
  - the job keeps no result, its excerpt is sealed from the log, and it expires with the reading;
  - no glossary entry for *read by AI*: the glossary is held to the on-screen `<Term>` words.

## What is next

- **14.7.8, the consultant build.**
- **#236:** vocabulary proposals from `unmatched`.

## Open questions

- **#238:** what a model's stored reply may keep. It holds the quoted evidence.
- **#239:** what the `ai` block means when AI work happened before the build.
- **Minors:** #240, #242, #247.
- **Gone after a machine restart, recreated:** the `walk-testdb` (`postgres:17-alpine`,
  `127.0.0.1:5442`, migrated with `make migrate MENDEL_DATABASE_URL=…`). The scratchpad's walk
  scripts were lost and rewritten.
