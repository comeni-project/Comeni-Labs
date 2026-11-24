# Three requests from the PI: forgetful stack, testable bundle, decisions report

**Status:** proposed, 2026-11-24. Remote runners (AWS, Azure, SSH), the fourth request, are a
separate project with their own issue and design.

The PI's audience is non-informatics. Each change is phrased in their terms: whether the app
remembers, whether a downloaded pipeline runs as it is, and why each choice was made.

Constraint for this round: the work is mechanical. It needs no app walk now; the browser
checks are saved for one walk over everything (listed at the end).

## 1. Memory: kept (default) or forgotten between runs

**Intent.** The stack keeps everything today: PostgreSQL and ClickHouse in named volumes, Mendel
and Wiener state under `.run/` and `workspace/`. The PI asked for a second mode in which
stopping the stack forgets everything. Kept stays the default.

**Design.**
- `.env`: `COMENI_MEMORY=kept` (default) or `forget`. It is documented in `.env.example`.
- `make dev`, `make prod` and their `-down` targets add `-f docker-compose.forget.yml` when it
  is `forget`. Compose stays the only way to run the app; this is not an image mode.
- The overlay puts PostgreSQL, Redis and ClickHouse data on `tmpfs`. **Named volumes are
  untouched**, so switching to `forget` and back loses nothing that was kept.
- The overlay points Mendel's and Wiener's state (drafts, forge, workspace, the Wiener run
  directory) at `.run/forget/…` instead of the kept paths. The Wiener run directory must be a
  host path at the same absolute path inside and outside (the worker's Docker socket mounts it
  into Nextflow's containers), so it cannot be `tmpfs`. Instead `make dev` empties
  `.run/forget/` before starting and `make dev-down` empties it after stopping.
- **Kept in both modes (my call):** the registry clone, downloaded models, and the ChatGPT
  sign-in. They are installation, not memory. Losing the sign-in would mean signing in
  again at every start. The data roots are read-only and never touched.
- Migrations run on start already, so an empty database works.

**Not built:** an image mode, a UI switch, or a way to keep one thing selectively.

**Checks.** A test that `docker compose -f … -f docker-compose.forget.yml config` gives every
stateful service a `tmpfs` or a `.run/forget` path and leaves named volumes unreferenced. A
manual check (on the walk): start in `forget`, build something, stop, start, and it is gone.

## 2. A testable bundle

**Intent.** The pipeline zip (`GET /api/pipeline/drafts/{id}/bundle`,
`mendel_api/services/bundle.py`) holds `pipeline.yml`, `main.nf`, `nextflow.config` and
`modules/`. Its config already has a `test` profile pinned to public example data, but a
samplesheet pipeline's `test` profile names `test-samplesheet.csv`, which only the gate writes.
So the downloaded zip cannot run its own test. The PI wants one download that runs.

**Approaches.**
- **A (recommended): the bundle carries the test samplesheet and a README.** Add
  `test-samplesheet.csv` (`emit.test_samplesheet`, already pure and deterministic) and
  `README.md`: what the pipeline does, and `nextflow run . -profile test,docker`. Nextflow
  downloads the pinned example files when the test runs. The zip stays small and deterministic,
  and Mendel's API makes no network calls.
- **B: the bundle carries the example files themselves**, downloaded by Mendel at bundle time
  into `test-data/`, with the samplesheet pointing at them. The test runs offline, but every
  download pulls megabytes through the API. A network adapter and a cache are needed, and the
  zip depends on a remote server being up.

Going with A unless the PI needs offline. The example data is public and pinned by commit, and
it is never anybody's samples, so no privacy rule is involved either way.

**Details.**
- The `test-samplesheet.csv` entry is only added when the pipeline takes a samplesheet and has
  a `test` profile (every input declares `test_data`). Otherwise the README says the
  pipeline has no runnable test and which inputs lack example data (the same list the config
  comment names).
- Wiener unpacks the same zip. The extra entries change the tree digest but not
  `pipeline_digest` (over `pipeline.yml`), so the runs-per-pipeline join is unaffected. The
  builder checks that Wiener's launcher does not collide with a file named `test-samplesheet.csv`.
- Determinism is preserved: fixed timestamps and sorted entries, as now.

**Checks.** Extend `packages/mendel-api/tests/pipelines/test_bundle.py`: the entries present,
the samplesheet equals `test_samplesheet(pipeline)`, two calls byte-identical. Optionally in
`make verify`: unzip and `nextflow run . -profile test,docker` on the RNA-seq example.

## 3. A decisions report

**Intent.** Every choice already carries its provenance (`Why`: tier, source, reason, premise
facts, layer, displaced layer, and any rule an AI choice overrode), and `pipeline.yml` holds the
decision records. The PI wants this readable by a person who does not read YAML: each
decision, who made it, and why.

**Approaches.**
- **A (recommended): a self-contained `decisions.html`**, rendered from `pipeline.yml` alone
  and laid out for print, so *Print → Save as PDF* makes the PDF. It is in the bundle and
  available on its own endpoint. No new dependency, and it opens anywhere.
- **B: a real `decisions.pdf`** through a PDF library (`fpdf2` is pure Python; WeasyPrint needs
  system libraries in the image). It is a PDF directly, at the cost of a dependency and layout
  code that is harder to keep deterministic.

Going with A. B can be added on top later if a printed file is not enough.

**Content, in order.**
1. The pipeline: its goal (intent), the steps in pipeline order, the registry layers pinned by
   digest.
2. For each step, its tool choice and settings: the value, **who decided** (rule, measured
   fact, registry default, the person, the AI), the reason, and the facts it rested on.
3. **Flagged for review** first: every tier-4 choice (an AI choice, a rule miss, a routing tie,
   an override), with the rule it overrode. It is never hidden, never collapsed.
4. A footer stating that the curated tools are reference material for a lab to validate, not a
   validated clinical test.

The words for tiers and sources reuse the served vocabulary (`comeni_core.plan.tiers`), not
new labels. No sample names, paths or file contents appear: the report reads only
`pipeline.yml`, which holds none.

**Where.** A pure renderer beside the emitter (`mendel_compiler/report.py`, from `Pipeline` to
HTML, deterministic, no clock). The bundle adds `decisions.html`, and
`GET /api/pipeline/drafts/{id}/decisions` serves it. The Build page gets a *Decisions report*
link next to the download. That one UI change is checked on the walk.

**Checks.** Unit tests on a fixture pipeline: every decision record and every `Why` appears;
tier-4 entries appear under *Flagged for review*; two renders are byte-identical; a reason with
`<script>` is escaped.

## Saved for the walk

- `forget` mode: start, build, stop, start, and it is empty. `kept`: it survives.
- Download a bundle, unzip, and `nextflow run . -profile test,docker` runs green.
- Open `decisions.html` from the Build page. It reads well, light and dark, and prints to PDF.
