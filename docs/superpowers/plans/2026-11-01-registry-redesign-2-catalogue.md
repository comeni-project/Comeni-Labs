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

- [x] Search with chips and grouped suggestions, in the address.
- [x] Format flow, with search on each side.
- [x] Your registry diagram, from the contracts.
- [x] Filters: status, topic bars with *No topic*, suites with search.
- [x] List rows with format pills; preview with what fits the registry.
- [x] First sync page.
- [x] Side-by-side comparison with the Catalogue and First sync boards at 1440 and 390, both themes.

## Compared with the boards

Live page against the Catalogue board, in dark at 1440 and 500 wide and light at 1440, on the real
2,126 modules, using headless Chrome. Fixed: a class clash that striped the flow, pills leading with
odd formats, the status strip's order, and the first-sync layout.

Differs from the board on purpose: the registry diagram is laid out from the server's links, so it
shows tools only, where the board hand-drew file types between them. Status labels stay the app's
(*Imported*, *Not imported*). The suggestions popover was tested but not seen rendered.

## Deviations

- Added `feeds` to `/registry/choices` and `fits` to a module's detail, so the page holds no rule.
- The `format` query parameter is gone; `reads` and `makes` replace it.
