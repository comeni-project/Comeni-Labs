# Registry · Tools: a filter panel, and pegi3s shown — plan

**Approved:** the operator, 2026-11-17 ("go ahead"; pegi3s shown, not imported; Topic in the panel only).

## Decisions

- **One filter panel**, as Outputs has, beside the results and in view while they scroll: search,
  Source, In your registry (several states at once), Takes, Makes (searchable lists), Topic
  (searchable, moved out of the rail), Tool family. Counts are the catalogue's facet counts.
- **Active filters as chips** above the results, each removable, and Clear all; all in the URL.
- **The format flow stays as an overview**: no explanatory sentence; clicking a format sets the
  panel's Takes or Makes.
- **pegi3s as a labelled preview**: a second catalogue source (`pegi3s`) holding a fixed sample of
  pegi3s Docker images, synced by the same job and stored as nf-core's are, each row marked
  `preview` and labelled so on the page. Never presented as a live connection; making it real is
  replacing the fixed list with a fetch. No version is claimed where the sample does not know it.

## Steps

- [x] API: `state` and `source` take several values; `ModuleRow.preview`; tests.
- [x] `mendel_forge.pegi3s.Pegi3sSample` (a `CatalogueSource` over a fixed list); synced after
      nf-core by `sync_catalogue_job`; tests.
- [x] Frontend: the filter panel, chips and Clear all; Topic out of the rail; the flow's caption
      gone and its clicks setting Takes/Makes; preview badge; tests.
- [ ] Checks, browser walk, commit, push.

## Deviations

- Active filters show as tokens in the existing search bar (sources and states added there), not a
  second chip row: the search bar already held format, topic and family tokens and its Clear all.
- A preview tool offers no Forge this ("Forging from pegi3s is not built yet."): nothing was synced,
  and the forge reads nf-core only.
- The format flow's title is "Formats"; `/catalogue/flow` now takes `source` too, so its bands follow
  the Source filter.
