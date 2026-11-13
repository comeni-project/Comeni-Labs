# Fixtures

`star/align`, `fastqc`, `bwa/mem` and `samtools/sort` are copied verbatim (meta.yml,
environment.yml, main.nf, tests/main.nf.test) from `nf-core/modules` at commit
`810182dd17d4b2bba8ec29ad825aef0084689f5a` (2026-10-29), MIT-licensed by the nf-core community.

`broken-meta` (a `meta.yml` that is not YAML), `no-environment` (fastqc without its
`environment.yml`) and `two-tools` (a tool named `foo` that no package is) are made by hand.

`samtools/faidx` is copied verbatim (meta.yml, environment.yml, main.nf; nf-core's tests are not
vendored) from this registry's `tools/nf-core/samtools/faidx/module`, itself `nf-core/modules` at
commit `9339809fcb90af8a8b7051e6cd914894d5c52002`, MIT-licensed by the nf-core community. It is
what the forge drafts a measurer for (#487).
