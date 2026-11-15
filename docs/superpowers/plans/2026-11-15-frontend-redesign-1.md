# Frontend redesign, part 1 (Welcome, Home, Data, Build, Run) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the redesign board's everyday path end to end. A person ticks folders on their own machine,
Comeni recognises samples, references and files and measures them, Build binds the pipeline's inputs to those
tables by type, and Run sends the analysis without a form. The whole path sits inside the new rail.

**Architecture:**
- An **analysis is a pipeline draft**. Its data lives in a new Mendel table, `analysis_data`, keyed by `draft_id`.
- Mendel reads files where they are, under configured **data roots** that are mounted read-only at identical
  absolute paths. A scan job reuses `samples_of` and `inspect_sample` on heads read from disk.
- The browser stays the courier. It asks Mendel for a run's bindings and posts them to Wiener, which refuses paths
  outside its own data roots.
- The frontend gains a `Rail`, an `AnalysisFrame` with `/a/:draft/…` routes, a new `data/` area, and restyled
  Home, Build and Run.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy + Alembic (`packages/mendel-api/migrations`), ARQ jobs (`mendel_api/jobs.py`),
  pytest.
- Frontend: React 19, react-router 7, TanStack Query and Virtual, Tailwind 4, Vitest, and the openapi-fetch
  clients (`make client`).

**Spec:** `docs/superpowers/specs/2026-11-15-frontend-redesign-design.md`. Read it, issue #511 with all its
comments, and the board sources in `docs/superpowers/specs/2026-11-15-frontend-redesign-board/` (see its
`README.md`). Each UI task names the board file it must match.

## Global Constraints

**Pipeline and data**
- No path in `pipeline.yml`, ever. Paths live only in `analysis_data` and in the params of a submitted run
  (invariant 15; `build/Sources.tsx` header).
- Never copy a person's file. Read at most `inspect.HEAD_BYTES` (4 MiB) per file for measuring.
- Hundreds of samples: no sample caps, keep facts only, stream the scan, and virtualise the tables
  (`@tanstack/react-virtual`).
- Every value shows its origin with the existing tags: MEASURED / RULE / DEFAULT / YOU / AI / NOT SET. AI changes
  stay marked AI until confirmed.

**Access, privacy and the boundaries**
- Path safety: every path a request names is resolved with `Path.resolve(strict=True)` and must sit under a
  configured data root. If not, refuse it with a coded diagnostic declared in
  `packages/comeni-core/src/comeni_core/diagnostics.yml` and emitted through `coded()`.
- Mounts: data roots are mounted **read-only**, at the same absolute path, into `api`, `mendel-worker` and
  `wiener-worker` (`docker-compose.yml`).
- Protection level: at level 0 the assistant may read file names and measured facts. Do not word privacy claims
  beyond `services/protection.py`.
- Cloud storage is not built. The rail shows a muted "Cloud storage · later".

**Interface copy and styling**
- No marketing copy and no assistant-voice sentences in the interface. Copy comes from the board files.
- Colours only through `tokens.css` tokens.
- Delete what a task replaces. There is no backward compatibility before v0.1.0, and old routes redirect.
- **Any existing code may change** (frontend or backend, its structure, names and APIs) when the new design fits
  better and code quality stays high. Treat the plan's file lists as a starting point, not as limits. Record each
  wider change as a ledger `Ruling:` line. The boundaries in `CLAUDE.md` still hold.

**Working rules**
- Tests:
  - Python tests: `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel
    WIENER_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener uv run pytest <path> -v`,
    after `make test-db`. Never bare `pytest`.
  - Frontend tests: `cd frontend && npx vitest run <path>`, and `npx tsc -b`.
- Use `git -C <repo>` for git. Never chain git after `cd`, and never `git stash`.
- Run checks in their own call before committing. Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- A defect found along the way gets a GitHub issue, linked as a sub-issue of #463, before it is fixed.
- Every UI task ends with a browser walk at 1440×900 and 390×844, compared to its board file. DOM tests do not
  establish layout.
- Full checks run once, at the end (Task 13): `make check`, `make guards`, `cd frontend && npx vitest run &&
  npx tsc -b`.

## Review Focus

1. **Symlinks and `..` escaping a data root.** A symlink inside a root that points outside it, or `path=../../etc`,
   must be refused by the tree and folder endpoints, not followed. Task 2 pins both.
2. **A folder that changes after the scan.** A file is deleted or renamed between the scan and the run. Bindings
   must report the missing file in `missing`, not send a dead path. Task 6 pins this.
3. **Mixed and odd data.** A folder with reads *and* assemblies, a lone `R1`, or the same sample name in two
   folders. The scan must keep every file, count the unfit ones, and number the duplicate names as `samples_of`
   does (`a#2`). Tasks 3 and 4 pin these.
4. **No model configured.** Data, the reading rule and the bindings must work fully without the assistant: the
   rule is deterministic, and the overlay says it needs a model. Task 9 pins this.
5. **Five hundred samples.** The scan must not hold file contents in memory beyond one head at a time, and the
   Samples table must render a 500-row fixture without mounting 500 rows. Tasks 3 and 8 pin these.

## Review checkpoints

There is no reviewer per task. A fresh reviewer, on the most capable model, reads the range since the last
checkpoint at each of these points, and execution waits for its findings:

| Checkpoint | After | What the reviewer checks above all |
|---|---|---|
| **A** | Task 3 | Path safety, the migration, the scan's memory use, and that no path reaches the draft |
| **B** | Task 6 | The rule and checks, plus bindings against the artifact's channels, and Wiener's guard |
| **C** | Task 9 | The Data UI against `Main.dc.html`, and the agent tools' AI marking and protection |
| **D** | Task 12 | Build and Run against their board files, and the end-to-end walk |
| **Final** | Task 13 | The whole branch |

At each checkpoint:
- Critical and Important findings are fixed, test first, before the next task.
- Minor findings go in the ledger, and then into one checklist issue under #512.

Cuts and deferrals are tracked in issue #512 and its sub-issues.

---

### Task 1: Tokens, the rail and the analysis frame

Board: all screens (the rail), `Tokens.dc.html`.

**Files:**
- Modify: `frontend/src/tokens.css`. Add `--ai`, `--ai-soft`, `--ai-line`, `--now-mid`, `--done-line`,
  `--measured-line`, `--needs-you-line`, `--report`, `--report-soft`, `--regions` and `--regions-soft`, in light and
  dark, with values from `Tokens.dc.html`. Map them in the Tailwind theme the same way the existing tokens are.
- Create: `frontend/src/app/rail/Rail.tsx`, `frontend/src/app/rail/Rail.test.tsx`.
- Create: `frontend/src/app/AnalysisFrame.tsx`.
- Modify: `frontend/src/app/Shell.tsx`. The top header goes and the grid becomes `[rail | page]`. Keep the settings
  overlay logic and `DOCS_URL`, and move `Jump` into the rail.
- Modify: `frontend/src/app/router.tsx`.

**Interfaces:**
- Produces:
  - `Rail({ slot, controls }: { slot?: ReactNode; controls?: { label: string; body: ReactNode } })`.
  - `AnalysisSlot({ draftId, page }: { draftId: string; page: "data" | "build" | "run" })` renders the switcher plus
    Data / Build / Run and the active page's sub-pages.
  - `AnalysisFrame` is the route element for `/a/:draft/*`. It provides `useAnalysis(): { draftId: string; name:
    string }`.
  - Routes:
    - `/a/:draft/data`, `/a/:draft/data/:sub` (`samples|references|files`).
    - `/a/:draft/build`.
    - `/a/:draft/run`, `/a/:draft/run/:run/:sub?` (`steps|outputs|console`).
  - Redirects:
    - `/build?draft=X` goes to `/a/X/build`.
    - `/runs` goes to `/`.
    - `/runs/:id` goes to `/a/:draft/run/:id` when a draft's digest matches the run's `pipeline_digest`, and
      otherwise renders the run inside the frame with an empty slot.

- [ ] **Step 1: Write the failing tests.** In `Rail.test.tsx`:
  - `places are always Home, Forge, Registry`
  - `the slot shows "Open an analysis…" when no analysis is open`
  - `inside an analysis the active page's sub-pages are indented under it` (Data shows Overview, Samples,
    References, Files)
  - `controls render under a divider with their label`
  - `the bottom row is Settings, theme, Local`
  - `collapsed rail hides labels and sub-pages`
- [ ] **Step 2:** Run `cd frontend && npx vitest run src/app/rail`. Expected: FAIL, module not found.
- [ ] **Step 3:** Implement `Rail`, `AnalysisSlot` and `AnalysisFrame`, then the router changes and the redirects.
  Remember the collapsed state in `localStorage` under `rail.mini`, wrapped in try/catch.
- [ ] **Step 4:** Run the same tests, plus `npx vitest run src/app && npx tsc -b`. Expected: PASS. Fix any
  existing tests that asserted the old header tabs. Delete them where they tested the header itself.
- [ ] **Step 5:** Walk it in the browser against the board's rail, in light and dark, expanded and collapsed.
- [ ] **Step 6:** Commit with the message `feat(frontend): the rail and the analysis frame (#511)`.

### Task 2: Data roots and the folder tree (backend)

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/settings.py`. Add `data_roots: list[Path]`, read from env
  `COMENI_DATA_ROOTS` (colon-separated, default empty).
- Create: `packages/mendel-api/src/mendel_api/services/data/roots.py`.
- Create: `packages/mendel-api/src/mendel_api/routes/data.py` with `router = APIRouter(prefix="/data",
  tags=["data"])`. Include it in `main.py` under `/api`.
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`. Add two codes, each the next free `MI02xx`: "path
  outside the data roots" and "no data roots configured".
- Modify: `docker-compose.yml`. Add `COMENI_DATA_ROOTS` to `api`, `mendel-worker` and `wiener-worker` (as
  `WIENER_DATA_ROOTS`), and mount each root `:ro` at the same path. A `.env` example line goes in
  `docs/how-to/` (the page that covers the dev stack).
- Test: `packages/mendel-api/tests/data/test_roots.py`.

**Interfaces:**
- Produces:
  - `inside_roots(path: str | Path, roots: list[Path]) -> Path`. This returns the resolved path or raises
    `ValueError(coded(...))`.
  - `list_folder(path: Path | None, roots: list[Path]) -> FolderListing`. `FolderListing = {path: str | None,
    folders: list[{name, path, files: int}], files: int}`. `path=None` lists the roots.
  - Endpoint `GET /api/data/tree?path=` (operation_id `readDataTree`).

- [ ] **Step 1: Write the failing tests** (use `tmp_path` roots):
  - `test_a_path_inside_a_root_resolves`
  - `test_dotdot_out_of_a_root_is_refused`
  - `test_a_symlink_pointing_outside_is_refused`
  - `test_no_roots_configured_is_refused_with_its_own_code`
  - `test_listing_counts_files_and_lists_subfolders_sorted`
  - `test_tree_route_without_path_lists_the_roots`
- [ ] **Step 2:** Run `… uv run pytest packages/mendel-api/tests/data/test_roots.py -v`. Expected: FAIL, import
  error.
- [ ] **Step 3:** Implement. Sort the folders by name. Count the files without reading them. Hidden entries
  (leading `.`) are left out.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with the message `feat(mendel-api): data roots and the folder tree (#511, #508)`.

### Task 3: Analysis data and the scan

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`. Add `AnalysisData`: `draft_id` (PK, FK
  `pipeline_draft.id`, on delete cascade), `folders` (Json list[str]), `scan` (Json: `{state:
  "idle"|"scanning"|"done"|"failed", done: int, total: int, error: str|None}`), `files` (Json list of
  `ScannedFile`), `samples` (Json list of `DataSample`), `rule` (Json), `references` (Json), `columns` (Json),
  `fixes` (Json), and `revision` (int).
- Create: an Alembic revision in `packages/mendel-api/migrations/versions/`.
- Create: `packages/mendel-api/src/mendel_api/services/data/types.py`:
  - `ScannedFile{path, name, size, recognised: str|None, used_as: str|None}`.
  - `DataSample{name, files: list[str] (paths), facts: list[SampleFact], left_out: bool, origin}`.
    `SampleFact` is reused from `mendel_api.authoring.types`.
- Create: `packages/mendel-api/src/mendel_api/services/data/scan.py`.
- Modify: `routes/data.py`.
- Modify: the job registry in `mendel_api/worker.py`. Register `scan_analysis_data`.
- Test: `packages/mendel-api/tests/data/test_scan.py`.

**Interfaces:**
- Consumes:
  - `inside_roots` (Task 2).
  - `sample_upload.samples_of(files, sizes)`.
  - `inspect.inspect_sample(files, stack, None, sizes=...)`.
  - `samples._agreed(inspections)`.
  - `decisions.observe(...)`, as `agent/direct.upload` does today.
- Produces:
  - `scan(draft_id: str) -> None`. This walks the ticked folders. It reads one head at a time
    (`open(..).read(HEAD_BYTES)`), pairs the files with the current rule (the default is `samples_of`), and
    inspects each sample. It stores the files, samples and facts, and records the agreed facts as MEASURED, unless
    the person already said them. It updates `scan.done` as it goes, and never raises: a failure sets
    `scan.state="failed"`.
  - `PUT /api/data/{draft_id}/folders` takes `{folders: list[str]}`. It validates each folder with
    `inside_roots`, stores them, sets `scan.state="scanning"`, enqueues `scan_analysis_data` with job id
    `scan:{draft_id}:{revision}`, and returns `AnalysisDataView`.
  - `GET /api/data/{draft_id}` (operation_id `readAnalysisData`) returns `AnalysisDataView`: everything except the
    file list, plus the counts.
  - `GET /api/data/{draft_id}/files?offset=&limit=` returns a page of `ScannedFile`.

- [ ] **Step 1: Write the failing tests.** Fixtures: a `tmp_path` root with paired FASTQ heads taken from the
  existing inspect fixtures in `packages/mendel-api/tests/authoring/samples/`.
  - `test_ticking_a_folder_outside_the_roots_is_refused`
  - `test_scan_pairs_r1_r2_into_samples_and_keeps_every_file`
  - `test_a_lone_r1_is_a_sample_of_its_own_and_counted_unfit`
  - `test_same_sample_name_in_two_folders_is_numbered`
  - `test_scan_records_agreed_facts_as_measured_but_not_over_the_persons_word`
  - `test_scan_reads_at_most_head_bytes_per_file`: patch `HEAD_BYTES` small, use a large file, and assert the bytes
    read.
  - `test_scan_of_500_files_holds_one_head_at_a_time`: wrap the reader and assert that at most one buffer is alive.
  - `test_a_failed_scan_says_so_and_does_not_raise`
  - `test_paths_never_reach_the_draft_artifact`: after the scan, the draft's `pipeline.yml` and its graph contain
    no scanned path.
- [ ] **Step 2:** Run `… uv run pytest packages/mendel-api/tests/data/test_scan.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the model, the migration, the scan, the routes and the job. Run `make client`, and
  commit the regenerated `frontend/src/api/`.
- [ ] **Step 4:** Run the tests again, and run `packages/mendel-api/tests/agent/test_samples.py`. Expected: PASS.
- [ ] **Step 5:** Commit with the message `feat(mendel-api): an analysis's data, scanned where it is (#511)`.

### Task 4: The reading rule, Check these, and fixes

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/data/rule.py`.
- Create: `packages/mendel-api/src/mendel_api/services/data/checks.py`.
- Modify: `routes/data.py`.
- Test: `packages/mendel-api/tests/data/test_rule.py`, `packages/mendel-api/tests/data/test_checks.py`.

**Interfaces:**
- Produces:
  - `Rule{pattern: str|None, origin: "rule"|"you"|"ai", confirmed: bool}`. `pattern=None` means the default
    mate-token pairing.
  - `apply_rule(names: list[str], rule: Rule) -> RuleResult{samples: list[(name, list[str])], unfit:
    list[str], examples: list[(file, sample, read|None)]}`. `examples` holds the first 3 fits.
  - Pattern grammar: literal text plus `{sample}` (one or more characters, not `/`) and `{read}` (`1` or `2`),
    matched against the file name, with compression and format suffixes allowed after it.
    Example: `{sample}_R{read}.fastq.gz`.
  - `checks(data: AnalysisData) -> list[Check{sample, kind: "missing_mate"|"odd_fact", detail, fixes:
    list[Fix]}]`.
  - `Fix{kind: "use_file"|"leave_out", sample, file: str|None}`.
  - `odd_fact` fires when a sample's value of a measured fact differs from the value most samples share (for
    example read length 50 versus 100).
  - `missing_mate` fires when a paired dataset has a sample with one file. It suggests unfit files whose stem
    shares the sample's prefix.
  - Endpoints:
    - `PUT /api/data/{id}/rule` takes `{pattern}`, origin `you`, and rescans the pairing without re-reading heads.
      This needs facts per file, so keep each file's inspection in `ScannedFile`.
    - `POST /api/data/{id}/rule/confirm` sets `confirmed=true`.
    - `POST /api/data/{id}/fixes` takes a `Fix`, applied and recorded with who.
  - `AnalysisDataView` gains `rule`, `rule_result` (counts plus examples) and `checks`.

- [ ] **Step 1: Write the failing tests.**
  - `test_default_rule_matches_samples_of`, which runs on the same names as
    `packages/mendel-api/tests/agent/test_samples.py`.
  - `test_pattern_sample_read_pairs_and_counts_unfit`
  - `test_pattern_without_read_makes_single_file_samples`
  - `test_bad_pattern_is_refused_with_a_coded_message`
  - `test_examples_are_the_first_three_fits`
  - `test_missing_mate_suggests_the_nearby_unfit_file`: `L17_R1.fastq.gz` alone, plus `L17_2.fq.gz` unfit, suggests
    `L17_2.fq.gz`.
  - `test_odd_fact_flags_the_half_length_sample`
  - `test_checks_are_neutral_for_assemblies`: a FASTA-only folder gives no `missing_mate`.
  - `test_use_file_fix_adds_the_mate_and_clears_the_check`
  - `test_leave_out_fix_keeps_the_sample_listed_but_out`
  - `test_a_persons_rule_is_tagged_you_and_unconfirmed_until_confirm`
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. The scan (Task 3) now calls `apply_rule` instead of `samples_of` directly. When the
  pattern is `None`, `apply_rule` delegates to `samples_of`, so the two never disagree.
- [ ] **Step 4:** Run `tests/data/` in full. Expected: PASS.
- [ ] **Step 5:** Commit with the message `feat(mendel-api): the reading rule, checks and fixes (#511)`.

### Task 5: References, columns and the Overview summary

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/data/summary.py`.
- Modify: `routes/data.py`.
- Test: `packages/mendel-api/tests/data/test_summary.py`.

**Interfaces:**
- Produces:
  - `POST /api/data/{id}/references` takes `{path}` (`inside_roots`). It inspects the file as a sample of one and
    stores `Reference{path, name, type_id, facts}`.
  - `DELETE /api/data/{id}/references/{index}`.
  - `PUT /api/data/{id}/columns` takes `{name, values: dict[sample, str]}`. A column named after a measured fact is
    refused.
  - `summary(data) -> Summary`. The Overview reads it as `AnalysisDataView.summary`.
    - `tiles`: `[{label, value}]`, in the order samples, kinds of data (distinct `type_id`), size on disk, files.
    - `compare_by`: the measured facts that have a numeric value on every sample, with `{measurement, label,
      values: [{sample, value}], median}`.
    - `measured`: each agreed fact with `{measurement, value, origin}`.
- **Copy:** labels come from the registry's measurement declarations (the same source `read_facts` uses), never
  hard-coded per data kind.

- [ ] **Step 1: Write the failing tests.**
  - `test_reference_from_a_file_is_inspected_and_kept`
  - `test_reference_outside_roots_is_refused`
  - `test_tiles_for_reads_and_for_assemblies_use_the_same_four_labels`
  - `test_compare_by_lists_only_numeric_facts_every_sample_has`
  - `test_compare_by_is_empty_when_nothing_numeric_was_measured`
  - `test_a_column_is_kept_per_sample`
  - `test_a_column_cannot_shadow_a_measured_fact`
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement, then run `make client`.
- [ ] **Step 4:** Run `tests/data/`. Expected: PASS.
- [ ] **Step 5:** Commit with the message `feat(mendel-api): references, columns and the data overview (#511)`.

### Task 6: Bindings, and Wiener's data roots

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/data/bindings.py`.
- Modify: `routes/data.py`.
- Modify: `packages/wiener-api/src/wiener_api/settings.py`. Add `data_roots`, from `WIENER_DATA_ROOTS`.
- Modify: `packages/wiener-api/src/wiener_api/routes/runs.py`. Add the path guard on `POST /runs`.
- Test: `packages/mendel-api/tests/data/test_bindings.py`, `packages/wiener-api/tests/test_data_roots.py`.

**Interfaces:**
- Consumes: the draft's saved artifact. Its `channels` hold `{name, type_id, param}`, and `input_form` is
  `direct` or `samplesheet`, with its columns (`comeni_core/artifact/pipeline.py:698`).
- Produces:
  - `bindings(draft_id) -> Bindings{params: dict[str, Any], missing: list[{channel, type_id, why}]}`.
  - A samplesheet channel gets rows built from the samples that are not left out. The rows have the artifact's
    columns: file paths, fact columns and person columns.
  - A direct channel is answered by the reference whose `type_id` matches, or by the single sample file of that
    type.
  - A channel nothing answers goes in `missing`.
  - A file that no longer exists goes in `missing` with `why="file not found"`. Check with `os.path.exists`.
  - Endpoint `GET /api/data/{id}/bindings` (operation_id `readRunBindings`).
  - Wiener: `POST /api/runs` refuses with 422 and a coded message when any string param that is an absolute path,
    or any samplesheet cell that is one, resolves outside `data_roots`. The existing `.run/wiener` work and
    artifact roots stay allowed.

- [ ] **Step 1: Write the failing tests.**
  - `test_samplesheet_rows_come_from_kept_samples_in_artifact_column_order`
  - `test_left_out_sample_is_not_bound`
  - `test_direct_reference_channel_bound_by_type`
  - `test_unanswered_channel_is_missing_with_its_type`
  - `test_deleted_file_after_scan_is_missing_not_sent`
  - `test_bindings_never_written_to_the_draft`
  - Wiener: `test_run_with_path_inside_data_roots_is_accepted`, `test_run_with_path_outside_is_refused`,
    `test_samplesheet_cell_outside_is_refused`.
- [ ] **Step 2:** Run both test files. Expected: FAIL.
- [ ] **Step 3:** Implement, then run `make client`. That regenerates both clients.
- [ ] **Step 4:** Run the tests again, plus `packages/wiener-api/tests/` in full. Expected: PASS.
- [ ] **Step 5:** Commit with the message `feat: a run's inputs come from the analysis's data (#508, #511)`.

### Task 7: Data · Overview, and the folder tree in the rail

Board: `Main.dc.html`, `dpage:'overview'`.

**Files:**
- Create: `frontend/src/data/useAnalysisData.ts`. This is a TanStack query of `readAnalysisData`. It polls every 2 s
  while `scan.state === "scanning"`.
- Create: `frontend/src/data/FolderTree.tsx`.
- Create: `frontend/src/data/Overview.tsx`.
- Create: `frontend/src/data/DataPage.tsx`, which switches on `:sub`.
- Test: `frontend/src/data/FolderTree.test.tsx`, `frontend/src/data/Overview.test.tsx`.

**Interfaces:**
- Consumes: `readDataTree`, `PUT …/folders`, `readAnalysisData` (Tasks 2, 3, 5), and `Rail` `controls` (Task 1)
  with the label "Folders".
- Produces: `FolderTree({ ticked, onTick })` lazy-loads children per folder. Below the tree sits the muted "Cloud
  storage · later" entry, which is not clickable.

- [ ] **Step 1: Write the failing tests.**
  - `ticking a folder PUTs the folder list and shows scanning progress`
  - `cloud storage is shown and disabled`
  - `overview tiles render from summary.tiles in order`
  - `compare-by picker lists summary.compare_by and draws one bar per sample`
  - `check these lists checks with their fixes`, and clicking a fix posts it
  - `an empty analysis shows only the folder prompt`
- [ ] **Step 2:** Run `npx vitest run src/data`. Expected: FAIL.
- [ ] **Step 3:** Implement against `Main.dc.html`. Use the Compare chart's layout and colours from the board.
- [ ] **Step 4:** Run the tests again, plus `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser. Tick a folder of real test FASTQs under a configured root and watch the
  scan finish. Compare with the board.
- [ ] **Step 6:** Commit with the message `feat(frontend): Data overview and folders (#511)`.

### Task 8: Data · Samples, References, Files

Board: `Main.dc.html`, `dpage:'samples' | 'refs' | 'files'`.

**Files:**
- Create: `frontend/src/data/Samples.tsx`, `frontend/src/data/ReadingRule.tsx`, `frontend/src/data/References.tsx`,
  `frontend/src/data/Files.tsx`.
- Test: `Samples.test.tsx`, `ReadingRule.test.tsx`, `References.test.tsx`, `Files.test.tsx` in `frontend/src/data/`.
- Delete: `frontend/src/build/Samplesheet.tsx` and its test, if nothing else imports them after Task 12. Otherwise
  delete them in Task 12.

**Interfaces:**
- Consumes: `PUT …/rule`, `…/rule/confirm`, `…/fixes`, `…/references`, `…/columns`, `…/files` (Tasks 3–5).
- Produces:
  - `Samples` columns are the sample name, then one column per file role (`read 1`, `read 2` for paired;
    otherwise `file`, from `files.length` and the recognised type), then each measured fact, then person columns.
  - Filters are All and To check. The table has a search box and highlights flagged rows.

- [ ] **Step 1: Write the failing tests.**
  - `reading rule shows three examples and the sample and unfit counts`
  - `looks right confirms; change the rule submits a pattern`
  - `an AI rule is tagged AI until confirmed`
  - `columns follow the data: paired reads get read 1 and read 2, assemblies one file`
  - `a 500-sample fixture mounts far fewer than 500 rows`, for virtualisation
  - `to check filter shows only flagged samples`
  - `add column prompts for a name and stores values`
  - `references: standard is shown as later; from a file opens the tree and posts the path`
  - `files lists recognised-as and used-as, paged`
- [ ] **Step 2:** Run `npx vitest run src/data`. Expected: FAIL.
- [ ] **Step 3:** Implement against the board.
- [ ] **Step 4:** Run the tests again, plus `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser, including 390 px wide, where the table scrolls inside its panel and the
  page does not.
- [ ] **Step 6:** Commit with the message `feat(frontend): Data samples, references and files (#511)`.

### Task 9: The assistant overlay, and the agent's data tools

Board: `Main.dc.html` (the assistant drawer).

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/data.py`, registered like `read.py`'s tools.
- Test: `packages/mendel-api/tests/agent/test_data_tools.py`.
- Create: `frontend/src/data/Assistant.tsx`, which reuses `build/living/ChatPanel.tsx` in a drawer.
- Test: `frontend/src/data/Assistant.test.tsx`.

**Interfaces:**
- Produces, as agent tools:
  - `read_data`: no arguments. It returns the summary, checks and the rule result. It returns names and facts
    only, never file contents.
  - `set_reading_rule`: `{pattern, reason}`. It is recorded with origin `ai` and unconfirmed.
  - `apply_fix`: `Fix` plus `reason`. It is recorded as the AI's, and shows AI in *Check these* until the person
    keeps it.
  - Each tool respects `protection.allows(...)` for the crossings it makes.
- Frontend:
  - `Assistant({ draftId })` is a fixed floating button. It opens a right-hand drawer over the page, using the
    analysis's builder session (the same one Build uses: `POST /pipeline/drafts/{id}/session`).
  - With no model configured (`useAiConfigured`), the drawer says "Needs a model" and links to
    `?settings=models`.

- [ ] **Step 1: Write the failing tests.**
  - `test_read_data_returns_names_and_facts_not_contents`
  - `test_set_reading_rule_is_ai_and_unconfirmed`
  - `test_apply_fix_records_ai_with_reason`
  - frontend: `drawer opens over the page and keeps page state`
  - frontend: `without a model the drawer says so and links to settings`
- [ ] **Step 2:** Run both. Expected: FAIL.
- [ ] **Step 3:** Implement. Add the tools to `prompt.md`'s tool list in one line each.
- [ ] **Step 4:** Run the tests again, plus `packages/mendel-api/tests/agent/`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser with the ChatGPT-subscription model. Ask "pair these by name" on a folder
  with an odd naming scheme.
- [ ] **Step 6:** Commit with the message `feat: the Data assistant and its tools (#511, #463)`.

### Task 10: Welcome and Home

Board: `Welcome.dc.html`, `Home.dc.html`.

**Files:**
- Create: `frontend/src/home/Welcome.tsx`, which replaces `First.tsx` (delete it and its test).
- Modify: `frontend/src/home/Home.tsx`, `Cards.tsx`, `Work.tsx`.
- Test: `frontend/src/home/Welcome.test.tsx`, `frontend/src/home/Home.test.tsx`.

**Interfaces:**
- Consumes: `listDrafts`, Wiener `/api/runs`, `readAnalysisData` per card (or a `data_summary` field added to
  `DraftsPage` rows if the per-card query is too chatty. **Prefer the field**: it is one query for the page), and
  `Rail` (Task 1).
- Produces:
  - **Welcome** has no rail. It shows the mark, *Omnes omnia omnino*, "What do you want to find out?" (`Describe`
    reused) and Add a folder. Add a folder creates a draft, then opens `/a/:id/data` with the tree open.
  - **Starters:** RNA-seq, isolate assembly, variants and metagenome. Also: start from a folder, open a pipeline
    file, and build by hand (which goes to `/a/:id/build`).
  - **Home** shows, in order: the question box with chips, Running now (with progress), Needs you, analysis cards
    with a Data / Build / Run strip and when each last changed, a New analysis card, and a This machine strip.
  - The rule *absence is absence* (the `Home.tsx` header) is kept: an empty band does not render.
  - The rail's controls on Home are "Recent".

- [ ] **Step 1: Write the failing tests.**
  - `no drafts renders Welcome without a rail`
  - `add a folder creates a draft and opens its data`
  - `an analysis card shows the data, build and run strip`
  - `running now and needs you are absent when empty`
  - `home never renders a contract id`. Keep the existing guard test passing.
- [ ] **Step 2:** Run `npx vitest run src/home`. Expected: FAIL.
- [ ] **Step 3:** Implement against the board. Add the faint pipeline drawing as inline SVG with tokens.
- [ ] **Step 4:** Run the tests again, plus `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser on an empty database (test stack) and a populated one.
- [ ] **Step 6:** Commit with the message `feat(frontend): Welcome and Home (#511)`.

### Task 11: Build in the analysis frame

Board: `Build.dc.html`.

**Files:**
- Modify: `frontend/src/app/BuildRoute.tsx`. It becomes `/a/:draft/build`. It opens the draft's session (reusing
  the existing `Opening` logic, keyed by `draftId`) and renders `LivingBuilder` with that session, with no
  `?session=` in the address.
- Modify: `frontend/src/build/living/LivingBuilder.tsx`, `LivingCanvas.tsx`, `LivingNode.tsx`, `StepCard.tsx`.
- Create: `frontend/src/build/panel/SidePanel.tsx` (Step | Assistant tabs), `frontend/src/build/panel/ToolForm.tsx`
  and `frontend/src/build/AddStep.tsx`, which replaces `Browse.tsx` (delete it and its test).
- Test: `SidePanel.test.tsx`, `ToolForm.test.tsx`, `AddStep.test.tsx`, plus updated `LivingNode`/`CanvasBoard`
  tests.

**Interfaces:**
- Consumes: the existing session APIs (`readStep`-style view the `StepCard` already uses), `ChatPanel`, the modules
  list (`/pipeline/modules`), and `Rail` controls, whose labels are "Review" and "On the steps".
- Produces:
  - `ToolForm({ step })` has Basic and Advanced sections. It renders a select, a number with unit and range, a
    yes/no, text, a file (bound to Data: it shows the bound reference, never a path box), a conditional and a
    repeat, from the step's settings. Each row has a one-line help, the source tag and **Ask AI**. Ask AI sends a
    scoped chat message, and the reply's value shows as AI until accepted.
  - On nodes: what the step does, then the tool and version, then labelled ports. Optional ports are hollow and
    dashed with Connect. Per-sample steps show ×N, and a fan-in port reads "all N", with N from the analysis's
    kept samples.
  - Right-click on a step opens `StepMenu`, which is reused. Right-click on the empty canvas offers Add step here.
  - **Pipeline file** stays reachable from the rail.

- [ ] **Step 1: Write the failing tests.**
  - `step tab and assistant tab switch without losing the chat draft`
  - `tool form splits basic and advanced`
  - `each control type renders from its setting kind`
  - `ask AI marks the suggested value AI until accepted`
  - `a file setting shows its Data binding, never a path input`. This extends `norule.test.ts`'s rule.
  - `optional ports are dashed with connect`
  - `a per-sample step shows ×N from the analysis's sample count`
  - `add step searches tools grouped by job and shows takes → makes`
- [ ] **Step 2:** Run `npx vitest run src/build`. Expected: FAIL.
- [ ] **Step 3:** Implement against the board. Measuring steps hanging under the step they read, and the shared
  trunk drawing, are in the board. Build them only if they fall out of the current layout. If not, note them for
  plan 2 in the ledger, not here.
- [ ] **Step 4:** Run the tests again, plus `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser: a QUAST-style step with many ports, and an RNA-seq build from Home's
  question box.
- [ ] **Step 6:** Commit with the message `feat(frontend): Build in the analysis frame (#511)`.

### Task 12: Run in the analysis frame, sent without a form

Board: `Run.dc.html`.

**Files:**
- Create: `frontend/src/runs/RunFrame.tsx` (the sub-page switch), `frontend/src/runs/Steps.tsx` (Graph | Timeline
  plus the shared `Tasks`), and `frontend/src/runs/Outputs.tsx`.
- Modify: `frontend/src/runs/Run.tsx`, which becomes the Overview page body, plus `Graph.tsx`, `Timeline.tsx` and
  `Tasks.tsx` (selection props).
- Modify: `frontend/src/build/useSubmit.ts`. It reads `readRunBindings` instead of a form.
- Delete: `frontend/src/build/RunSheet.tsx` and the `SubmitForm` part of `Submit.tsx`, with their tests.
- Delete: `frontend/src/runs/Board.tsx`. Home and the rail replace it.
- Test: `Steps.test.tsx`, `RunFrame.test.tsx`, an updated `useSubmit` test.

**Interfaces:**
- Consumes: `readRunBindings` (Task 6), the Wiener run endpoints (`/runs/{id}/overview|graph|timeline|tasks|results|
  events`), and `Rail` controls with the label "Runs of this analysis". These are the runs whose
  `pipeline_digest` equals the draft's digest.
- Produces:
  - **Run** (`/a/:draft/run`): with no runs it shows the bindings summary ("24 samples, 1 reference") and **Run**.
    When `missing` is non-empty, Run is disabled and each missing item links to the Data page that fixes it.
  - **Steps:** `selected` step id kept in the URL (`useUrlState("step")`), so switching between Graph and Timeline
    keeps it highlighted. The tasks panel under either view shows one row per sample with status, attempt, time,
    memory and note, plus filters and sample search.
  - **Overview:** status first (N of M samples, to go, retries), a live mini pipeline, *Worth a look*, results so
    far, and This machine.

- [ ] **Step 1: Write the failing tests.**
  - `run is disabled while bindings report missing, and each links to data`
  - `sending posts the bindings' params to wiener, with no form`
  - `selected step survives switching graph to timeline`
  - `clicking a gantt bar selects that step's tasks`
  - `the rail lists only this analysis's runs`
- [ ] **Step 2:** Run `npx vitest run src/runs src/build/useSubmit`. Expected: FAIL.
- [ ] **Step 3:** Implement against the board. Reuse `Graph`, `Timeline`, `Tasks`, `Console`, `OverviewPanel` and
  `Measured`, and restyle them to the tokens.
- [ ] **Step 4:** Run the tests again, plus `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Walk it in the browser on the dev stack. Tick a folder under the data root, build, run, and watch
  Steps in both views. This is the end-to-end success path in the spec.
- [ ] **Step 6:** Commit with the message `feat(frontend): Run in the analysis frame, inputs from Data (#511, #508)`.

### Task 13: Clean-up, docs and full checks

**Files:**
- Delete: components no route reaches any more. Find them with `cd frontend && npx tsc -b` plus a search for
  imports of each file under `build/`, `home/` and `runs/`.
- Modify: `docs/` user pages that describe the old header, the run sheet or upload-as-input. Follow
  `docs/how-to/development/documentation.md`, and give the data roots setup one home.
- Modify: `CHANGELOG.md`, with entries under `frontend`, `mendel-api` and `wiener-api`.
- Modify: `docs/notes/now.md`.

- [ ] **Step 1:** Run `make check`. Expected: PASS.
- [ ] **Step 2:** Run `make guards`. Expected: PASS. If a guard fails, follow the guard-ledger procedure; never
  loosen a guard to pass.
- [ ] **Step 3:** Run `cd frontend && npx vitest run && npx tsc -b`. Expected: PASS.
- [ ] **Step 4:** Walk the whole path again in the browser at both viewports, in light and dark, and compare every
  page with its board file.
- [ ] **Step 5:** Commit with the message `docs: the redesigned everyday path (#511)`. Close #508 if the walk
  passed, and tick #511's part-1 items.
