# Fixtures

`star/align`, `fastqc`, `bwa/mem` and `samtools/sort` are copied verbatim (meta.yml,
environment.yml, main.nf, tests/main.nf.test) from `nf-core/modules` at commit
`810182dd17d4b2bba8ec29ad825aef0084689f5a` (2026-10-29), MIT-licensed by the nf-core community.

`broken-meta` (a `meta.yml` that is not YAML), `no-environment` (fastqc without its
`environment.yml`) and `two-tools` (a tool named `foo` that no package is) are made by hand.
