# Forge MVP 3: explicit families (#441)

Approved in the working session: add Family declarations to Vocabulary, with human approval
and registry loader validation at Assembly. Reuse the core Family schema; the family is the
first segment of a type ID. Preserve pending draft ownership and change propagation.

- [x] Reproduce `assembly.fasta` failing without its family and passing with an explicit family.
- [x] Add typed family values, constructors, AI context and draft writing.
- [x] Track pending family dependencies and reopen affected dependent items on change.
- [x] Verify Python behavior, generated schemas, frontend tests and browser at both widths/themes.
- [x] Prepare the reviewed change for CI and merge; GPU acceptance stays in #412.

No live models or tools are required for this change. Use isolated fixtures and test databases.

The two-STAR draft test exposed an independent tuple-key displacement failure, recorded as
#448. The family dependency guard uses STAR and BWA to isolate this change. No protocol
change or workaround for #448 is included.

Verification: 974 Python checks passed across Forge, Forge API, core and guards, with required
DB coverage. All 996 frontend tests passed; the final constructor adjustment passed its 16
targeted tests and TypeScript. Generated clients are unchanged after regeneration. Lint,
generated types, documentation sizes, links and source paths passed. Browser verification at
1440/390 in light/dark covered Family creation, refusal retention and the saved declaration;
no page errors or horizontal page overflow. Screenshots were inspected.

Regression evidence is recorded in `tests/fixtures/guard-ledger.md`. CI and merge delivery are
tracked on #441 and its pull request. No live GPU/model/tool acceptance has been claimed.
