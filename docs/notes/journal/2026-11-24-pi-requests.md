# 2026-11-24: forget mode, a testable bundle, a decisions report (#619)

[The plan](../../superpowers/plans/2026-11-24-pi-requests.md), from
[the design](../../superpowers/specs/2026-11-24-pi-requests-design.md). Three of the PI's four
requests; remote runs (AWS, Azure, SSH) are #618, designed separately.

## Where things stand

- **`COMENI_MEMORY=forget`** (default `kept`): Make adds `docker-compose.forget.yml` last.
  Databases on `tmpfs`; Mendel's drafts, forge and workspace and Wiener's run directory under
  `.run/forget/`, emptied before start and after stop. Named volumes are never referenced.
  The registry clone, ChatGPT sign-in and models are kept in both modes. A bad value stops
  every `make` target.
- **The zip runs its own test**: it carries `README.md`, and `test-samplesheet.csv` for a
  samplesheet pipeline whose inputs all declare `test_data`; otherwise the README names the
  inputs that lack one (`emit.test_profile_missing`).
- **Decisions report**: `mendel_compiler.report.render`, one self-contained, printable HTML
  page from `pipeline.yml`; tier-4 choices first with any overridden rule. In the zip as
  `decisions.html`, at `GET /api/pipeline/drafts/{id}/decisions`, and as **Zip** and
  **Decisions** links on Build's pipeline file once kept.
- `make check` 4172 passed, `make guards` 84, vitest 694. `make verify` not run (machine busy).

## Left for the walk

- `forget`: start, build, stop, start, and it is empty; `kept` survives; switching loses nothing.
  Watch for root-owned files under `.run/forget/wiener` making `rm -rf` fail at `dev-down`.
- Download **Zip**, unzip, `nextflow run . -profile test,docker` runs green.
- **Decisions** reads well light and dark and prints to PDF on A4; the links sit well in the
  pipeline file's toolbar at desktop and phone widths.

## Traps

- Compose merges volume entries **by target**: an overlay replaces a mount by naming its target.
  YAML puts no tag on an alias, so `!override *x` fails; restate the list.
- `mendel_compiler.emit` is shadowed by the `emit` function its `__init__` exports; import from
  the module path. A `test_*` function imported into a test module is collected: alias it.
