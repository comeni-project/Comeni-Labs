# 2026-10-29 — Forge part 1: the catalogue and the tool page

[The plan](../../superpowers/plans/2026-10-29-forge-1-catalogue.md) and
[the design](../../superpowers/specs/2026-10-29-forge-1-catalogue-design.md), on
`forge-1-catalogue`, for #362 (and #363's tool page) and #410.

## Where things stand

- **Decided (operator):** the tool page belongs in part 1; the pull request states are
  placeholders until #366; everything nf-core declares is extracted; a registry module without a
  contract is a mistake to refuse, not a state to show (#410).
- **Found:** three registry modules (`picard/markduplicates`, `samtools/faidx`, `bedtools/sort`)
  had nf-core source and no contract since the old forge's drafting targets (2026-08-17).
  `MD0025` now refuses them; comeni-registry#22 removed them (merged 2026-10-29).
  The submodule points at its merge.
- **Found:** the issues number the forge one ahead of the design (the tool page is "MVP 2",
  #363). The design's part numbers are used in the code and pages; issue numbers in prose.
- Built: `mendel-forge` (source interface, nf-core blobless clone, parser, topics, state);
  `catalogue_sync` and `catalogue_module` with a daily sync; the catalogue and tool-page API;
  the Registry tab, catalogue page and tool page.
- The new package reuses the name `mendel_forge`, so part 0's guard now names the old package's
  modules and routes rather than the package.
- `test_blueprint_lookup_refuses_unknown_steps` fails on `main` too; not this work's.
- Not merged, not pushed.
