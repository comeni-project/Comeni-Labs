# Recorded upstream responses

Shaped like the real APIs, small enough to read. CI reaches no source — acceptance criterion 17
— so these are what the adapter tests run against.

**Not captured verbatim from upstream.** A real nf-core tree response is ~40,000 entries and a
real Docker Hub namespace listing is ~190 repositories with every tag; committing either would
be a fixture nobody reads and a diff nobody reviews. These are hand-built to the documented
response *shape*, with the fields the adapters actually read, and the cases that matter:

| fixture | the case it carries |
|---|---|
| `nfcore_tree.json` | a nested tool (`samtools/sort`), a directory with only `main.nf`, and a `tests/` directory — the two things that must **not** count as modules |
| `nfcore_tree_truncated.json` | `truncated: true`, which must make the sync refuse rather than report a short total |
| `nfcore_meta_*.yml` | a real `meta.yml` shape, including the nested `input`/`output` blocks and the `meta` Groovy map that is never a port |
| `pegi3s_repositories.json` | one paged listing, including a repository with **no** matching source directory |
| `pegi3s_tags_*.json` | a semver tag beside `latest`, a tag with no manifest, and a repository whose only tag is `latest` |
| `pegi3s_source_tree.json` | the `pegi3s/dockerfiles` tree, deliberately missing one tool that Docker Hub lists |

**Counts in the tests are derived from these files, never written as literals.** A test asserting
`len(items) == 3` passes when the fixture changes and the adapter breaks; a test asserting it
equals the number of directories in the fixture holding both required files is checking the
adapter. That rule is the plan's, and it is the difference between a fixture test and a
transcription.
