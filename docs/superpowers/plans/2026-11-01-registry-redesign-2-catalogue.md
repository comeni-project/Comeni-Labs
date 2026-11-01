# Registry redesign, slice 2: the Catalogue

**Spec:** [slice 2 and D4](../specs/2026-10-31-registry-redesign-design.md). **Branch:**
`registry-redesign-2-catalogue`. **Size:** L.

## Server

- [x] `topics.py`: format aliases, and formats only mentioned in a description.
- [x] `catalogue_module`: `formats_in`, `formats_out`, `mentions_in`, `mentions_out` replace `formats`.
- [x] `read_page`: `reads`, `makes`, `suite`, `no_topic`, `mentioned`; a facet's count leaves out its
      own pick, and `wider` says how many a mention would add.
- [x] `GET /forge/catalogue/flow`: how the formats on show connect.

## Page

- [ ] Search with chips and grouped suggestions, in the address.
- [ ] Format flow, with search on each side.
- [ ] Your registry diagram, from the contracts.
- [ ] Filters: status, topic bars with *No topic*, suites with search.
- [ ] List rows with format pills; preview with what fits the registry.
- [ ] First sync page.
- [ ] Side-by-side comparison with the Catalogue and First sync boards at 1440 and 390, both themes.
