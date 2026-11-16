# Frontend redesign, part 1 (Welcome, Home, Data, Build, Run) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the redesign board's everyday path end to end. A person ticks folders on their own machine.
Comeni recognises the samples, references and files in them and measures them. Build connects the pipeline's
inputs to those tables by type, and Run sends the analysis without a form. All of it sits inside the new rail.

**Architecture:**
- **An analysis is a pipeline draft.** Its data lives in a new Mendel table, `analysis_data`, keyed by `draft_id`.
  That table is the **only** place samples live: the chat session's `samples` column and upload-as-samples are
  removed.
- **Files are read in place.** Mendel reads them where they are, under configured data roots. The roots are mounted
  read-only, at the same absolute path, in Mendel and in Wiener.
- **A scan job** reads each file's head and reuses `samples_of` and `inspect_sample`. It records the agreed facts
  through the same code path the builder already reads, so resolution, routing, emission and the #463 agent loop
  are unchanged (spec, "One engine, one loop").
- **Running.** The browser asks Mendel for a run's bindings and posts them to Wiener. Wiener refuses paths outside
  its own data roots.
- **Frontend.** New `ui/` primitives, a `Rail`, an `AnalysisFrame` with `/a/:draft/…` routes, and one folder per
  analysis page: `analysis/data`, `analysis/build` and `analysis/run`.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy and Alembic (`packages/mendel-api/migrations`), ARQ jobs (`mendel_api/jobs.py`,
  `worker.py`), and pytest.
- Frontend: React 19, react-router 7, TanStack Query and Virtual, Tailwind 4 (`@theme` in `main.css`), Vitest, and
  the openapi-fetch clients (`make client`).

**Spec:** `docs/superpowers/specs/2026-11-15-frontend-redesign-design.md`. Before starting, read it, issue #511 with
all its comments, and the board sources in `docs/superpowers/specs/2026-11-15-frontend-redesign-board/` (see that
folder's `README.md`). Each UI task names the board file it must match. The cuts are tracked in #512.

## Global Constraints

**Paths and data**
- **No path in `pipeline.yml`, ever.** Paths live only in `analysis_data` and in the params of a submitted run
  (invariant 15; see the header of `build/Sources.tsx`).
- **Never copy a person's file.** Read at most `inspect.HEAD_BYTES` (4 MiB) of each file for measuring.
- **Hundreds of samples.** No sample caps, keep facts only, stream the scan, and virtualise the tables
  (`@tanstack/react-virtual`).
- **Every value shows where it came from,** with the existing tags: MEASURED / RULE / DEFAULT / YOU / AI / NOT SET.
  An AI change stays marked AI until it is confirmed.

**Safety and privacy**
- **Path safety.** Resolve every path a request names with `Path.resolve(strict=True)`. It must sit under a
  configured data root. If it does not, refuse it with a coded diagnostic, declared in
  `packages/comeni-core/src/comeni_core/diagnostics.yml` and emitted through `coded()`.
- **Mounts.** Data roots are mounted **read-only**, at the same absolute path, into `api`, `mendel-worker` and
  `wiener-worker` (`docker-compose.yml`).
- **Protection.** The scan is gated by `Crossing.UPLOAD` in `services/protection.py`, documented as "a sample's
  head reaches this server". Once the upload route is gone (Task 4), rename it to `SAMPLE_HEAD`.
  At level 0 the assistant may read file names and measured facts. Do not word any privacy claim beyond what
  `protection.py` implements.
- **Cloud storage** is not built. The rail shows a muted "Cloud storage · later" (#516).

**Interface**
- **No marketing copy** and no sentences in the assistant's voice anywhere in the interface. Copy comes from the
  board files.
- **Colours** come only from `tokens.css` tokens, and **shared pieces** come only from the `ui/` primitives
  (Task 2).

**Code changes**
- **Any existing code may change,** frontend or backend, including its structure, names and APIs, when the new
  design fits better and code quality stays high. The plan's file lists are a starting point, not a limit. Record
  each wider change as a ledger `Ruling:` line. The boundaries in `CLAUDE.md` still hold.
- **Delete what a task replaces.** There is no backward compatibility before v0.1.0, and old routes redirect.

**Tests**
- Python: `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel
  WIENER_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener uv run pytest <path> -v`, after
  `make test-db`. Never run bare `pytest`. In the steps below, `…` stands for this prefix.
- Frontend: `cd frontend && npx vitest run <path>` and `npx tsc -b`.
- Each task runs only its own targeted tests. The full checks run once, in Task 15.

**Git and issues**
- Use `git -C <repo>`. Never chain git after `cd`, and never use `git stash`.
- Run checks in their own call, before the commit.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- A defect found along the way gets an issue first, as a sub-issue of #463, before it is fixed.

**Browser walks**
- Every UI task ends with a browser walk at 1440×900 and at 390×844, in light and dark, compared with its board
  file. DOM tests do not establish layout.

## Review Focus

1. **A path that escapes a data root.** Symlinks and `..`: a symlink inside a root pointing outside it, or
   `path=../../etc`, must be refused by the tree and folder endpoints, not followed. Task 3 pins this.
2. **A folder that changed after the scan.** If a file was deleted or renamed between the scan and the run, the
   bindings must report it in `missing`, not send a dead path. Task 7 pins this.
3. **Mixed and odd data.** For reads mixed with assemblies, a lone R1, or the same sample name in two folders, the
   scan must keep every file, count the files that fit no sample, and number duplicate names as `samples_of` does
   (`a#2`). Tasks 4 and 5 pin this.
4. **No model configured.** Data, the reading rule and the bindings must all work without the assistant: the rule
   is deterministic, and the overlay says it needs a model. Task 10 pins this.
5. **Five hundred samples.** The scan must hold at most one file head in memory at a time, and the Samples table
   must render a 500-row fixture without mounting 500 rows. Tasks 4 and 9 pin this.

## Review checkpoints

There is no reviewer per task. At each checkpoint, a fresh reviewer on the most capable model reads the range of
commits since the last checkpoint, and execution waits for its findings.

| Checkpoint | After | What the reviewer checks above all |
|---|---|---|
| **A** | Task 4 | The primitives' API; path safety; the migration; the scan's memory use; that no path reaches the draft; one source of samples |
| **B** | Task 7 | The reading rule and checks; the bindings against the artifact's channels; Wiener's guard |
| **C** | Task 10 | The Data pages against `Main.dc.html`; whether the agent tools mark their changes AI and respect protection |
| **D** | Task 14 | Build and Run against their board files; the end-to-end walk |
| **Final** | Task 15 | The whole branch |

Critical and Important findings are fixed test-first before the next task starts. Minor findings go into the
ledger, and then into one checklist issue under #512.

---

### Task 1: Tokens, the rail and the analysis frame

Board: all screens (the rail) and `Tokens.dc.html`.

**Files:**
- Modify: `frontend/src/tokens.css`. Add `--ai`, `--ai-soft`, `--ai-line`, `--now-mid`, `--done-line`,
  `--measured-line`, `--needs-you-line`, `--report`, `--report-soft`, `--regions` and `--regions-soft`, in light and
  dark, with the values from `Tokens.dc.html`.
- Modify: `frontend/src/main.css`. Map the new tokens in `@theme`, the way the existing ones are mapped.
- Create: `frontend/src/app/rail/Rail.tsx` and `frontend/src/app/rail/Rail.test.tsx`.
- Create: `frontend/src/app/AnalysisFrame.tsx`.
- Modify: `frontend/src/app/Shell.tsx`:
  - Remove the top header. The grid becomes `[rail | page]`.
  - Keep the settings overlay logic and `DOCS_URL`.
  - `Jump` moves into the rail.
- Modify: `frontend/src/app/router.tsx`.

**Interfaces:**
- Produces:
  - `Rail({ slot, controls }: { slot?: ReactNode; controls?: { label: string; body: ReactNode } })`.
  - `AnalysisSlot({ draftId, page }: { draftId: string; page: "data" | "build" | "run" })`. It shows the analysis
    switcher, then Data / Build / Run, with the active page's sub-pages under it.
  - `AnalysisFrame`, the route element for `/a/:draft/*`. It provides
    `useAnalysis(): { draftId: string; name: string }`.
  - Routes:
    - `/a/:draft/data`
    - `/a/:draft/data/:sub`, where `:sub` is `samples`, `references` or `files`
    - `/a/:draft/build`
    - `/a/:draft/run`
    - `/a/:draft/run/:run/:sub?`, where `:sub` is `steps`, `outputs` or `console`
  - Redirects:
    - `/build?draft=X` goes to `/a/X/build`.
    - `/runs` goes to `/`.
    - `/runs/:id` goes to `/a/:draft/run/:id` when a draft's `digest` equals the run's `pipeline_digest`.
      Otherwise the run renders inside the frame, with an empty slot.

- [x] **Step 1:** Write the failing tests in `Rail.test.tsx`:
  - `places are always Home, Forge, Registry`
  - `the slot shows "Open an analysis…" when no analysis is open`
  - `inside an analysis the active page's sub-pages are indented under it`: Data shows Overview, Samples,
    References and Files.
  - `controls render under a divider with their label`
  - `the bottom row is Settings, theme, Local`
  - `collapsed rail hides labels and sub-pages`
- [x] **Step 2:** Run `cd frontend && npx vitest run src/app/rail`. Expected: FAIL, module not found.
- [x] **Step 3:** Implement `Rail`, `AnalysisSlot` and `AnalysisFrame`, then the router and the redirects. Keep the
  collapsed state in `localStorage` under the key `rail.mini`, wrapped in try/catch.
- [x] **Step 4:** Run the rail tests, then `npx vitest run src/app && npx tsc -b`. Expected: PASS. Existing tests
  that test the old header itself are deleted, not adapted.
- [x] **Step 5:** Walk it in the browser and compare it with the board's rail, expanded and collapsed.
- [x] **Step 6:** Commit: `feat(frontend): the rail and the analysis frame (#511)`.

### Task 2: UI primitives

Board: every screen. Compare how each piece repeats across `Main`, `Build`, `Run` and `Home`.

**Files:**
- Create: in `frontend/src/ui/`, `Panel.tsx`, `SourceTag.tsx`, `Tabs.tsx`, `Segmented.tsx`, `Drawer.tsx`,
  `Tile.tsx` and `DataTable.tsx`, plus one test file per component.
- Modify: existing `ui/` components that overlap with these. Merge them or delete them. For example, a source tag
  might already exist as `ui/spelled` or a provenance chip; search before creating.

**Interfaces:**
- Produces:
  - `Panel({ title?, actions?, children })`.
  - `SourceTag({ source }: { source: "measured" | "rule" | "default" | "you" | "ai" | "not_set" })`. Its colours
    are `--measured*`, `--ai*`, `--needs-you*` and so on, and its labels are the uppercase words above.
  - `Tabs({ tabs: {id, label}[], value, onChange })`. It uses `role="tablist"` and arrow keys move between tabs.
  - `Segmented({ options, value, onChange })`. Each option is a button with `aria-pressed`. It replaces the
    hand-rolled group in `home/Home.tsx`.
  - `Drawer({ open, onClose, side: "right", children })`. Esc closes it, and focus returns to the opener.
  - `Tile({ label, value, hint? })`.
  - `DataTable<T>({ rows, columns: {id, header, cell(row), width?}[], rowKey, highlight?(row), height })`. It is
    virtualised with `@tanstack/react-virtual`.

- [x] **Step 1:** Write the failing tests:
  - `source tag renders each source with its label`
  - `tabs move with arrow keys`
  - `segmented marks the pressed option`
  - `drawer closes on Escape and returns focus`
  - `data table with 500 rows mounts far fewer than 500 row elements`
  - `data table highlights rows the predicate marks`
- [x] **Step 2:** Run `npx vitest run src/ui`. Expected: FAIL.
- [x] **Step 3:** Implement against the board's look. Replace the duplicates the search found, and ledger each
  merge.
- [x] **Step 4:** Run `npx vitest run src/ui src/home && npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Commit: `feat(frontend): the shared pieces of the redesign (#511)`.

### Task 3: Data roots and the folder tree (backend)

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/settings.py`. Add `data_roots: list[Path]`, read from the
  colon-separated env var `COMENI_DATA_ROOTS`. The default is empty.
- Create: `packages/mendel-api/src/mendel_api/services/data/__init__.py` and `roots.py` in the same folder.
- Create: `packages/mendel-api/src/mendel_api/routes/data.py`, with
  `router = APIRouter(prefix="/data", tags=["data"])`. Include it in `main.py` under `/api`.
- Modify: `diagnostics.yml`. Add two codes, each taking the next free `MI02xx` number: "path outside the data
  roots" and "no data roots configured".
- Modify: `docker-compose.yml`:
  - Set `COMENI_DATA_ROOTS` on `api` and `mendel-worker`, and `WIENER_DATA_ROOTS` on `wiener-worker`.
  - Mount each root `:ro`, at the same path.
  - Put the `.env` setup in the how-to page that covers the dev stack: one place, linked from elsewhere.
- Test: `packages/mendel-api/tests/data/test_roots.py`.

**Interfaces:**
- Produces:
  - `inside_roots(path: str | Path, roots: list[Path]) -> Path`. It returns the resolved path, or raises
    `ValueError(coded(...))`.
  - `list_folder(path: Path | None, roots: list[Path]) -> FolderListing`, where
    `FolderListing = {path: str | None, folders: list[{name, path, files: int}], files: int}`. With `path=None` it
    lists the roots.
  - The route `GET /api/data/tree?path=`, with operation_id `readDataTree`.

- [x] **Step 1:** Write the failing tests. Use `tmp_path` folders as the roots.
  - `test_a_path_inside_a_root_resolves`
  - `test_dotdot_out_of_a_root_is_refused`
  - `test_a_symlink_pointing_outside_is_refused`
  - `test_no_roots_configured_is_refused_with_its_own_code`
  - `test_listing_counts_files_and_lists_subfolders_sorted`
  - `test_tree_route_without_path_lists_the_roots`
- [x] **Step 2:** Run `… uv run pytest packages/mendel-api/tests/data/test_roots.py -v`. Expected: FAIL, import
  error.
- [x] **Step 3:** Implement:
  - Sort folders by name.
  - Count files without reading them.
  - Leave out hidden entries, meaning names that start with `.`.
- [x] **Step 4:** Run the tests again. Expected: PASS.
- [x] **Step 5:** Commit: `feat(mendel-api): data roots and the folder tree (#511, #508)`.

### Task 4: Analysis data, the scan, and one source of samples

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`:
  - Add `AnalysisData` with these columns:
    - `draft_id`: the primary key, FK `pipeline_draft.id`, on delete cascade
    - `folders`: Json `list[str]`
    - `scan`: Json `{state: "idle"|"scanning"|"done"|"failed", done: int, total: int, error: str|None}`
    - `files`: Json list of `ScannedFile`
    - `samples`: Json list of `DataSample`
    - `rule`, `references`, `columns`, `fixes`: Json
    - `revision`: int
  - **Remove** `PipelineAuthoringSession.samples`.
- Create: an Alembic revision in `packages/mendel-api/migrations/versions/`. It creates the table and drops the
  column. Nothing existing is migrated: there are no users before v0.1.0.
- Create: `services/data/types.py`:
  - `ScannedFile{path, name, size, recognised: str|None, used_as: str|None, inspection: Inspection|None}`. The
    inspection is kept so that changing the rule can re-pair the files without reading them again.
  - `DataSample{name, files: list[str], facts: list[SampleFact], left_out: bool, origin}`. `SampleFact` stays in
    `mendel_api.authoring.types` and is imported from there, because moving it would make `authoring` import
    `services`.
- Create: `services/data/scan.py` and `services/data/record.py`.
- Modify: `routes/data.py`, and `mendel_api/worker.py`, where the job `scan_analysis_data` is added to
  `functions`.
- **Move the samples to the data table:**
  - `agent/direct.upload`'s recording (`decisions.observe` with MEASURED, and the `changes.apply` input) moves into
    `record.py`.
  - `agent/samples.py` and the upload function in `agent/direct.py` are deleted, along with the route
    `uploadAuthoringSample` in `routes/authoring.py` and its tests.
  - `agent/read.py` (`read_facts`) and `agent/view.py` read samples from `AnalysisData`.
  - The agent's question shape `"upload"` (`agent/ask.py`, `authoring/types.py`) becomes `"data"`: the question
    points the person at Data, and its answer is the scan's result.
  - `services/sample_upload.py` keeps only `samples_of` and its helpers. Move them to `services/data/pairing.py`
    and delete the multipart reader.
- Test: `packages/mendel-api/tests/data/test_scan.py`, plus the agent tests that change with this
  (`tests/agent/test_samples.py` and `test_direct.py` move to `tests/data/`, or are deleted where they tested
  upload).

**Interfaces:**
- Consumes:
  - `inside_roots` (Task 3)
  - `pairing.samples_of(files, sizes)`
  - `inspect.inspect_sample(files, stack, None, sizes=...)`
- Produces:
  - `record.agreed(inspections) -> Inspection`. This is the former `_agreed`.
  - `record.record_measured(draft_id: str, agreed: Inspection, *, who: str) -> list[str]`. It records the facts
    the samples agree on as MEASURED, unless the person already said them, sets the input type, and returns the
    measurements it recorded.
  - `scan(draft_id: str) -> None`. It:
    - checks the protection crossing;
    - walks the ticked folders;
    - reads one head at a time (`open(...).read(HEAD_BYTES)`);
    - pairs the files with the current rule (Task 5; until then, `samples_of`);
    - inspects each sample and stores the files, samples and facts;
    - calls `record_measured`;
    - updates `scan.done` as it goes.

    It never raises: a failure sets `scan.state="failed"`.
  - `PUT /api/data/{draft_id}/folders`, with body `{folders: list[str]}`. It checks each folder with
    `inside_roots`, stores them, sets `scan.state="scanning"`, enqueues `scan_analysis_data` with the job id
    `scan:{draft_id}:{revision}`, and returns an `AnalysisDataView`.
  - `GET /api/data/{draft_id}`, operation_id `readAnalysisData`. It returns an `AnalysisDataView`: everything
    except the file list, plus counts.
  - `GET /api/data/{draft_id}/files?offset=&limit=`. It returns a page of `ScannedFile`, without `inspection`.

- [x] **Step 1:** Write the failing tests. The fixtures are a `tmp_path` root holding paired FASTQ heads copied
  from `packages/mendel-api/tests/authoring/samples/`.
  - `test_ticking_a_folder_outside_the_roots_is_refused`
  - `test_scan_pairs_r1_r2_into_samples_and_keeps_every_file`
  - `test_a_lone_r1_is_a_sample_of_its_own_and_counted_unfit`
  - `test_same_sample_name_in_two_folders_is_numbered`
  - `test_scan_records_agreed_facts_as_measured_but_not_over_the_persons_word`, which ports the upload test's
    assertion.
  - `test_scan_reads_at_most_head_bytes_per_file`: patch `HEAD_BYTES` small, scan a large file, and assert how many
    bytes were read.
  - `test_scan_of_500_files_holds_one_head_at_a_time`: wrap the reader and assert that at most one buffer is alive
    at once.
  - `test_a_failed_scan_says_so_and_does_not_raise`
  - `test_scan_refused_when_protection_forbids_inspection`
  - `test_paths_never_reach_the_draft_artifact`: after a scan, the draft's `pipeline.yml` and graph contain no
    scanned path.
  - `test_read_facts_lists_samples_from_the_data_table`
  - `test_upload_route_is_gone`: the route answers 404 or 405.
- [x] **Step 2:** Run `… uv run pytest packages/mendel-api/tests/data/test_scan.py -v`. Expected: FAIL.
- [x] **Step 3:** Implement the model, the migration, `record`, the scan, the routes, the job and the move. Then
  run `make client` and commit the regenerated `frontend/src/api/`.
- [x] **Step 4:** Run `tests/data/` and `packages/mendel-api/tests/agent/`. Expected: PASS.
- [x] **Step 5:** Fix the frontend the move breaks:
  - `useAuthoringSession.upload` and `AgentQuestion`'s upload shape go.
  - The `"data"` shape renders a link to `/a/:draft/data`.

  Run `npx vitest run src/build && npx tsc -b`. Expected: PASS.
- [x] **Step 6:** Commit:
  `feat: an analysis's data, scanned where it is; samples live only there (#511)`.

**→ Checkpoint A.**

### Task 4b (inserted 2026-11-16, operator): Facts derived, rules cleaned up

Done, outside the original plan, from Checkpoint A's finding 4 and the operator's rules audit:

- [x] Facts and inputs about the data are derived from `analysis_data` at every `decisions.read`, never logged
  (`services/data/facts.py`). A person's or the AI's word stands. A finished scan rebuilds the pipeline.
- [x] Protection levels, their checks and setting, MI0213 and MI0214 are removed. A posture is #71.
- [x] The characterisation door (door 6), its payload and `SampleText` are removed.
- [x] Shape versions are removed in both services: stamps, load checks, goldens, MI0400 and MW0100.
- [x] Invariants 3, 14 and 15, the tiers section and the public claims are rewritten. `CLAUDE.md`'s
  issue-first rule now covers only defects outside the plan.

**Consequences for later tasks:**
- Task 5 rewrites pairing only. Facts already follow the data.
- Task 7's samplesheet fact columns read each sample's own value for a fact that *varies*.
- Tasks 12–14 show source tags (MEASURED / RULE / DEFAULT / YOU / AI / NOT SET), never tier colours.

### Task 5: The reading rule, Check these, and fixes

**Files:**
- Create: `services/data/rule.py` and `services/data/checks.py`.
- Modify: `routes/data.py` and `scan.py`. The scan pairs files with `apply_rule`.
- Test: `packages/mendel-api/tests/data/test_rule.py` and `test_checks.py`.

**Interfaces:**
- Produces:
  - `Rule{pattern: str|None, origin: "rule"|"you"|"ai", confirmed: bool}`. `pattern=None` means the default
    mate-token pairing.
  - `apply_rule(names: list[str], rule: Rule) -> RuleResult`, where
    `RuleResult{samples: list[(name, list[str])], unfit: list[str], examples: list[(file, sample, read|None)]}`.
    `examples` holds the first three files that fit.
  - Pattern grammar: literal text plus two tokens, matched against the file name; compression and format suffixes
    may follow.
    - `{sample}`: one or more characters, not `/`
    - `{read}`: `1` or `2`
    - Example: `{sample}_R{read}.fastq.gz`
  - `checks(data) -> list[Check{sample, kind: "missing_mate"|"odd_fact", detail, fixes: list[Fix]}]`, where
    `Fix{kind: "use_file"|"leave_out", sample, file: str|None}`.
    - `odd_fact`: a sample's measured value differs from the value most samples share, for example a read length of
      50 against 100.
    - `missing_mate`: in paired data, a sample with only one file. It suggests unfit files whose stem shares the
      sample's prefix.
  - Routes:
    - `PUT /api/data/{id}/rule`, body `{pattern}`. The origin is `you`. It re-pairs the files from the stored
      inspections, without reading them again.
    - `POST /api/data/{id}/rule/confirm` sets `confirmed=true`.
    - `POST /api/data/{id}/fixes`, body `Fix`. The fix is applied and recorded with who made it.
  - `AnalysisDataView` gains `rule`, `rule_result` (counts and examples) and `checks`.

- [x] **Step 1:** Write the failing tests:
  - `test_default_rule_matches_samples_of`
  - `test_pattern_sample_read_pairs_and_counts_unfit`
  - `test_pattern_without_read_makes_single_file_samples`
  - `test_bad_pattern_is_refused_with_a_coded_message`
  - `test_examples_are_the_first_three_fits`
  - `test_missing_mate_suggests_the_nearby_unfit_file`: `L17_R1.fastq.gz` alone with an unfit `L17_2.fq.gz`
    suggests `L17_2.fq.gz`.
  - `test_odd_fact_flags_the_half_length_sample`
  - `test_checks_are_neutral_for_assemblies`: a folder of only FASTA files gives no `missing_mate`.
  - `test_use_file_fix_adds_the_mate_and_clears_the_check`
  - `test_leave_out_fix_keeps_the_sample_listed_but_out`
  - `test_a_persons_rule_is_tagged_you_and_unconfirmed_until_confirm`
  - `test_changing_the_rule_does_not_reread_files`
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement. With `pattern=None`, `apply_rule` delegates to `samples_of`, so the two can never
  disagree.
- [x] **Step 4:** Run `tests/data/`. Expected: PASS.
- [x] **Step 5:** Commit: `feat(mendel-api): the reading rule, checks and fixes (#511)`.

### Task 6: References, columns and the Overview summary

**Files:**
- Create: `services/data/summary.py`.
- Modify: `routes/data.py`.
- Test: `packages/mendel-api/tests/data/test_summary.py`.

**Interfaces:**
- Produces:
  - `POST /api/data/{id}/references`, body `{path}`, checked with `inside_roots`. It inspects the file as a sample
    of one and stores `Reference{path, name, type_id, facts}`.
  - `DELETE /api/data/{id}/references/{index}`.
  - `PUT /api/data/{id}/columns`, body `{name, values: dict[sample, str]}`. A column named after a measured fact is
    refused.
  - `summary(data) -> Summary`, exposed as `AnalysisDataView.summary`:
    - `tiles`: `[{label, value}]`, in the order samples, kinds of data (distinct `type_id`), size on disk, files.
    - `compare_by`: each measured fact with a numeric value on every sample, as
      `{measurement, label, values: [{sample, value}], median}`.
    - `measured`: each agreed fact, as `{measurement, value, origin}`.
  - **Labels** come from the registry's measurement declarations, the same source `read_facts` uses. They are never
    hard-coded per kind of data.

- [x] **Step 1:** Write the failing tests:
  - `test_reference_from_a_file_is_inspected_and_kept`
  - `test_reference_outside_roots_is_refused`
  - `test_tiles_for_reads_and_for_assemblies_use_the_same_four_labels`
  - `test_compare_by_lists_only_numeric_facts_every_sample_has`
  - `test_compare_by_is_empty_when_nothing_numeric_was_measured`
  - `test_a_column_is_kept_per_sample`
  - `test_a_column_cannot_shadow_a_measured_fact`
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement, then run `make client`.
- [x] **Step 4:** Run `tests/data/`. Expected: PASS.
- [x] **Step 5:** Commit: `feat(mendel-api): references, columns and the data overview (#511)`.

### Task 7: Bindings, and Wiener's data roots

**Files:**
- Create: `services/data/bindings.py`.
- Modify: `routes/data.py`.
- Modify: `packages/wiener-api/src/wiener_api/settings.py`. Add `data_roots`, read from `WIENER_DATA_ROOTS`.
- Modify: `packages/wiener-api/src/wiener_api/routes/runs.py`. `submit` (`POST /runs`, line 282) checks paths.
- Test: `packages/mendel-api/tests/data/test_bindings.py` and `packages/wiener-api/tests/test_data_roots.py`.

**Interfaces:**
- Consumes the draft's saved artifact:
  - `channels`: `{name, type_id, param}`
  - `input_form`: `direct` or `samplesheet`, with its columns (`comeni_core/artifact/pipeline.py:698`)
- Produces `bindings(draft_id) -> Bindings{params: dict[str, Any], missing: list[{channel, type_id, why}]}`:
  - A samplesheet channel gets one row per sample that is not left out, in the artifact's column order: file paths,
    then fact columns, then person columns.
  - A direct channel is answered by the reference whose `type_id` matches, or by the single sample file of that
    type.
  - A channel nothing answers goes into `missing`.
  - A file that no longer exists (checked with `os.path.exists`) goes into `missing` with `why="file not found"`.
- The route is `GET /api/data/{id}/bindings`, operation_id `readRunBindings`.
- **Wiener:** `POST /api/runs` refuses with 422 and a coded message if any absolute-path string param, or any
  samplesheet cell, resolves outside `data_roots`. Paths under the existing `.run/wiener` work and artifact roots
  stay allowed.

- [x] **Step 1:** Write the failing tests:
  - `test_samplesheet_rows_come_from_kept_samples_in_artifact_column_order`
  - `test_left_out_sample_is_not_bound`
  - `test_direct_reference_channel_bound_by_type`
  - `test_unanswered_channel_is_missing_with_its_type`
  - `test_deleted_file_after_scan_is_missing_not_sent`
  - `test_bindings_never_written_to_the_draft`
  - On the Wiener side:
    - `test_run_with_path_inside_data_roots_is_accepted`
    - `test_run_with_path_outside_is_refused`
    - `test_samplesheet_cell_outside_is_refused`
- [x] **Step 2:** Run both test files. Expected: FAIL.
- [x] **Step 3:** Implement, then run `make client`. This regenerates both clients.
- [x] **Step 4:** Run the tests again, then all of `packages/wiener-api/tests/`. Expected: PASS.
- [x] **Step 5:** Commit: `feat: a run's inputs come from the analysis's data (#508, #511)`.

**→ Checkpoint B.**

### Task 8: Data · Overview, and the folder tree in the rail

Board: `Main.dc.html` with `dpage:'overview'`.

**Files:**
- Create in `frontend/src/analysis/data/`:
  - `useAnalysisData.ts`: a TanStack query of `readAnalysisData`. It polls every 2 s while
    `scan.state === "scanning"`.
  - `FolderTree.tsx`
  - `Overview.tsx`
  - `DataPage.tsx`, which switches on `:sub`
- Test: `FolderTree.test.tsx` and `Overview.test.tsx`, beside them.

**Interfaces:**
- Consumes: `readDataTree`, `PUT …/folders` and `readAnalysisData` (Tasks 3, 4 and 6); the `Rail` `controls`, with
  the label "Folders"; and the `ui/` primitives.
- Produces:
  - `FolderTree({ ticked, onTick })`. It lazy-loads the children of each folder.
  - Below the tree, a muted "Cloud storage · later" that cannot be clicked.

- [x] **Step 1:** Write the failing tests:
  - `ticking a folder PUTs the folder list and shows scanning progress`
  - `cloud storage is shown and disabled`
  - `overview tiles render from summary.tiles in order`
  - `compare-by picker lists summary.compare_by and draws one bar per sample`
  - `check these lists checks with their fixes`: clicking a fix posts it.
  - `an empty analysis shows only the folder prompt`
- [x] **Step 2:** Run `npx vitest run src/analysis/data`. Expected: FAIL.
- [x] **Step 3:** Implement against `Main.dc.html`. The Compare chart takes its layout and colours from the board.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser. Tick a folder of real test FASTQ files under a configured root, and watch
  the scan finish.
- [x] **Step 6:** Commit: `feat(frontend): Data overview and folders (#511)`.

### Task 9: Data · Samples, References, Files

Board: `Main.dc.html` with `dpage:'samples' | 'refs' | 'files'`.

**Files:**
- Create in `frontend/src/analysis/data/`: `Samples.tsx`, `ReadingRule.tsx`, `References.tsx` and `Files.tsx`, each
  with a test file beside it.
- Delete: `frontend/src/build/Samplesheet.tsx` and its test. Anything that still imports it is replaced by the
  Data tables in Task 14.

**Interfaces:**
- Consumes: `PUT …/rule`, `…/rule/confirm`, `…/fixes`, `…/references`, `…/columns` and `…/files` (Tasks 4–6); and
  `DataTable`, `SourceTag` and `Segmented`.
- Produces the `Samples` table:
  - Columns: the name; one column per file role (`read 1` and `read 2` for paired data, otherwise `file`, decided
    from `files.length` and the recognised type); each measured fact; then the person's columns.
  - Filters: All and To check.
  - A search box.
  - Flagged rows are highlighted.

- [x] **Step 1:** Write the failing tests:
  - `reading rule shows three examples and the sample and unfit counts`
  - `looks right confirms; change the rule submits a pattern`
  - `an AI rule is tagged AI until confirmed`
  - `columns follow the data: paired reads get read 1 and read 2, assemblies one file`
  - `a 500-sample fixture mounts far fewer than 500 rows`
  - `to check filter shows only flagged samples`
  - `add column prompts for a name and stores values`
  - `references: standard is shown as later; from a file opens the tree and posts the path`
  - `files lists recognised-as and used-as, paged`
- [x] **Step 2:** Run `npx vitest run src/analysis/data`. Expected: FAIL.
- [x] **Step 3:** Implement against the board.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser, including at 390 px. At that width the table scrolls inside its panel,
  never the page.
- [x] **Step 6:** Commit: `feat(frontend): Data samples, references and files (#511)`.

### Task 10: The assistant overlay, and the agent's data tools

Board: the assistant drawer in `Main.dc.html`.

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/data.py`, registered the same way as the tools in `read.py`.
- Test: `packages/mendel-api/tests/agent/test_data_tools.py`.
- Create: `frontend/src/analysis/Assistant.tsx`. It reuses `ChatPanel` inside the `Drawer` primitive.
- Test: `Assistant.test.tsx`, beside it.

**Interfaces:**
- Produces three agent tools:
  - `read_data`, no arguments. It returns the summary, the checks and the rule result: names and facts only, never
    file contents.
  - `set_reading_rule`, with `{pattern, reason}`. It records the rule with origin `ai`, unconfirmed.
  - `apply_fix`, with a `Fix` plus a `reason`. It is recorded as the AI's, and shows AI in *Check these* until the
    person keeps it.

  Each tool respects `protection.allows(...)` for the crossings it makes.
- `Assistant({ draftId })`:
  - It is a fixed floating button. It opens a right-hand drawer over the page, on the analysis's builder session:
    the same session Build uses, `POST /pipeline/drafts/{id}/session`.
  - It is mounted on Data now and on Build in Task 12, where Build's Assistant tab may embed the same chat. The
    ledger records which.
  - With no model (`useAiConfigured`), the drawer says "Needs a model" and links to `?settings=models`.

- [x] **Step 1:** Write the failing tests:
  - `test_read_data_returns_names_and_facts_not_contents`
  - `test_set_reading_rule_is_ai_and_unconfirmed`
  - `test_apply_fix_records_ai_with_reason`
  - On the frontend:
    - `drawer opens over the page and keeps page state`
    - `without a model the drawer says so and links to settings`
- [x] **Step 2:** Run both test files. Expected: FAIL.
- [x] **Step 3:** Implement. Add the three tools to the tool list in `prompt.md`, one line each.
- [x] **Step 4:** Run the tests and `packages/mendel-api/tests/agent/`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser with the ChatGPT-subscription model. Ask "pair these by name" on a folder
  with an odd naming scheme.
- [x] **Step 6:** Commit: `feat: the Data assistant and its tools (#511, #463)`.

**→ Checkpoint C.**

### Task 11: Welcome and Home

Board: `Welcome.dc.html` and `Home.dc.html`.

**Files:**
- Create: `frontend/src/home/Welcome.tsx`. It replaces `First.tsx`: delete `First.tsx` and its test.
- Modify (rewrite freely): `frontend/src/home/Home.tsx`, `Cards.tsx` and `Work.tsx`.
- Modify: `packages/mendel-api` `listDrafts`. Add `data_summary` (sample count, kinds, scan state, last changed) to
  each `DraftsPage` row, so the page makes one query and not one per card.
- Test: `Welcome.test.tsx` and `Home.test.tsx`, plus a mendel-api test of `data_summary`.

**Interfaces:**
- Consumes: `listDrafts` with `data_summary`; Wiener's `/api/runs`; `Rail` (Task 1); and the `ui/` primitives.
- Produces:
  - **Welcome:**
    - It has no rail.
    - It shows the mark, *Omnes omnia omnino*, "What do you want to find out?" (reusing `Describe`) and Add a
      folder. Add a folder creates a draft and opens `/a/:id/data` with the tree open.
    - Starters cover RNA-seq, isolate assembly, variants and metagenome. There are also: start from a folder, open
      a pipeline file, and build by hand, which goes to `/a/:id/build`.
  - **Home**, in this order:
    - the question box, with chips
    - Running now, with progress
    - Needs you
    - the analysis cards, each with a Data / Build / Run strip and when it last changed
    - a New analysis card
    - a This machine strip

    Absence is absence: an empty band does not render. The rail's controls on Home are labelled "Recent".

- [x] **Step 1:** Write the failing tests:
  - `no drafts renders Welcome without a rail`
  - `add a folder creates a draft and opens its data`
  - `an analysis card shows the data, build and run strip from data_summary`
  - `running now and needs you are absent when empty`
  - `home never renders a contract id`. This keeps the existing guard.
  - `test_drafts_page_rows_carry_data_summary`
- [x] **Step 2:** Run `npx vitest run src/home` and the mendel-api test. Expected: FAIL.
- [x] **Step 3:** Implement against the board. The faint pipeline drawing is inline SVG that uses the tokens.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser, on an empty test stack and on a populated one.
- [x] **Step 6:** Commit: `feat: Welcome and Home (#511)`.

### Task 12: Build · the page, its panel and the tool form

Board: `Build.dc.html`: the frame, the right panel and the Step tab.

**Files:**
- Create in `frontend/src/analysis/build/`:
  - `BuildPage.tsx`, for `/a/:draft/build`. It opens the draft's session, carrying over the `Opening` logic from
    `app/BuildRoute.tsx`, keyed by `draftId`, so the address never shows `?session=`.
  - `SidePanel.tsx` (Step | Assistant tabs) and `ToolForm.tsx`.
- Move into `analysis/build/`, rewriting what no longer fits: the living-builder pieces the page still uses
  (`LivingBuilder`, `ChatPanel`, `AgentThread`, `StepCard`, `useAuthoringSession` and their helpers).
- Delete: `app/BuildRoute.tsx`, plus whatever the move leaves with no importer.
- Test: `SidePanel.test.tsx` and `ToolForm.test.tsx`. Existing tests move with their components.

**Interfaces:**
- Consumes: the existing session APIs and step view (what `StepCard` reads); the `Rail` controls, with the labels
  "Review" and "On the steps", plus Pipeline file; and the `ui/` primitives, `Tabs` and `SourceTag`.
- Produces `ToolForm({ step })`:
  - Basic and Advanced sections.
  - A control for each kind of setting: select, number with unit and range, yes/no, text, file, conditional and
    repeat. A **file** setting shows its Data binding, never a path box.
  - On every row: a one-line help, the source tag, and **Ask AI**. Ask AI sends a chat message scoped to that
    setting, and the value it suggests shows as AI until accepted.

- [x] **Step 1:** Write the failing tests:
  - `step tab and assistant tab switch without losing the chat draft`
  - `tool form splits basic and advanced`
  - `each control type renders from its setting kind`
  - `ask AI marks the suggested value AI until accepted`
  - `a file setting shows its Data binding, never a path input`. Also extend `build/norule.test.ts`'s rule to
    cover `analysis/`.
- [x] **Step 2:** Run `npx vitest run src/analysis/build src/build`. Expected: FAIL.
- [x] **Step 3:** Implement against the board.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser: an RNA-seq build started from Home's question box.
- [x] **Step 6:** Commit: `feat(frontend): Build's page, panel and tool form (#511)`.

### Task 13: Build · the canvas and Add step

Board: `Build.dc.html`: the nodes, the ports and the picker.

**Files:**
- Move into `analysis/build/canvas/`, rewriting what no longer fits: `LivingCanvas`, `LivingNode`, `StepMenu`,
  `Port` and the geometry helpers.
- Create: `frontend/src/analysis/build/AddStep.tsx`. It replaces `build/Browse.tsx`; delete `Browse.tsx` and its
  test.
- Test: `AddStep.test.tsx`, and the node and canvas tests, moved and updated.

**Interfaces:**
- Consumes: `/pipeline/modules`, and the analysis's count of samples that are not left out (`readAnalysisData`).
- Produces:
  - **Nodes:** what the step does, then the tool and version, then labelled ports.
  - **Ports:** an optional port is hollow and dashed, with Connect. A per-sample step shows ×N, and a fan-in port
    reads "all N".
  - **Right-click:** on a step it opens `StepMenu`; on the empty canvas it offers Add step here.
  - **Add step:** a searchable picker over the canvas, grouped by job, that shows what each tool takes and makes.

- [x] **Step 1:** Write the failing tests:
  - `optional ports are dashed with connect`
  - `a per-sample step shows ×N from the analysis's sample count`
  - `a fan-in port reads all N`
  - `right-click on the empty canvas offers add step here`
  - `add step searches tools grouped by job and shows takes → makes`
- [x] **Step 2:** Run `npx vitest run src/analysis/build`. Expected: FAIL.
- [x] **Step 3:** Implement against the board. The measuring step hung under the step it reads, and the shared
  trunk, are tracked in #517. Build them here only if they fall out of the layout; if they do not, ledger that.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk it in the browser: a QUAST-style step with many ports, and adding a step by right-clicking.
- [x] **Step 6:** Commit: `feat(frontend): Build's canvas and Add step (#511)`.

### Task 14: Run in the analysis frame, sent without a form

Board: `Run.dc.html`.

**Files:**
- Create in `frontend/src/analysis/run/`: `RunPage.tsx` (the sub-page switch), `Overview.tsx`, `Steps.tsx`
  (Graph | Timeline above one shared tasks panel), `Outputs.tsx` and `Console.tsx`.
- Move or rewrite from `frontend/src/runs/`: `Graph`, `Timeline`, `Tasks`, `TaskRow`, `Console`, `OverviewPanel`,
  `Measured`, `useRunStream`, `Failure`, `Cancel` and `DeleteRun`. `runs/` itself is gone at the end of this task.
- Move and rewrite `build/useSubmit.ts` as `analysis/run/useSend.ts`. It reads `readRunBindings` instead of a form.
- Delete: `build/RunSheet.tsx`, `build/Submit.tsx` and `runs/Board.tsx`, with their tests.
- Test: `Steps.test.tsx`, `RunPage.test.tsx` and `useSend.test.ts`.

**Interfaces:**
- Consumes: `readRunBindings` (Task 7); Wiener's run endpoints
  (`/runs/{id}/overview|graph|timeline|tasks|results|events`); and the `Rail` controls, labelled "Runs of this
  analysis", which list runs whose `pipeline_digest` equals the draft's `digest`.
- Produces:
  - `/a/:draft/run` with no runs: the bindings summary ("24 samples, 1 reference") and **Run**. When `missing` is
    not empty, Run is disabled and each missing item links to the Data page that fixes it.
  - **Steps:** the selected step is kept in the URL (`useUrlState("step")`), so it stays highlighted when switching
    between Graph and Timeline. The tasks panel shows one row per sample, with status, attempt, time, memory and
    note, plus filters and a sample search.
  - **Overview:**
    - status first: N of M samples, how many to go, retries
    - a live mini pipeline
    - *Worth a look*
    - the results so far
    - This machine

- [x] **Step 1:** Write the failing tests:
  - `run is disabled while bindings report missing, and each links to data`
  - `sending posts the bindings' params to wiener, with no form`
  - `selected step survives switching graph to timeline`
  - `clicking a gantt bar selects that step's tasks`
  - `the rail lists only this analysis's runs`
- [x] **Step 2:** Run `npx vitest run src/analysis/run`. Expected: FAIL.
- [x] **Step 3:** Implement against the board.
- [x] **Step 4:** Run the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Walk `docs/how-to/development/demo-walk.md` in the browser on the dev stack, beats 1–8, after
  `python3 tools/demo_data.py`. This is the spec's success path from end to end, and the demo's rehearsal. Fix
  the script where the product is right and the script is wrong; file an issue where the product is wrong.
- [x] **Step 6:** Commit: `feat(frontend): Run in the analysis frame, inputs from Data (#511, #508)`.

### Task 14b: Data and References, reworked to the walk's board

Board: claude.ai/artifact/QS7zEVF1dfe8ncpZ4dPjFn (approved 2026-11-16). Added after the walk of
Task 14 step 5; the walk's findings are #526–#532.

**Files:** `routes/data.py` and `services/data/roots.py` (each folder says what it looks like;
`GET /data/readers`); `frontend/src/analysis/data/` (DataPage, a new `Start.tsx` and
`References.tsx` rewritten, Overview reduced to the checks and the side cards, Samples on the
Data page); `app/rail/AnalysisSlot.tsx` (Data's sub-pages: Samples, References, All files).

- [x] **Step 1:** Tests first: a folder's `looks_like` counts files by the kind a reader or a
  study-wide type names, a reference folder's FASTA as a genome; `/data/readers` lists each
  format reader with its extensions and what it measures; Data with nothing ticked shows the
  folder picker on the page and "Read these folders" ticks what was chosen; checks are grouped
  one row a sample; a fact column draws a bar, amber only where that measurement is flagged;
  References shows one slot a study-wide input of Build's canvas, offers files from the
  folders ranked by kind, and "Use as" adds the reference.
- [x] **Step 2:** Run them. Expected: FAIL.
- [x] **Step 3:** Implement against the board.
- [x] **Step 4:** Run the data tests, `npx vitest run`, `npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Look at both demo analyses in the browser at desktop and phone width. (Desktop done; the window would not shrink to phone width here: carried to Task 15 step 4.)
- [x] **Step 6:** Commit: `feat: Data and References to the board (#511)`.

**→ Checkpoint D.**

### Task 15: Clean-up, docs and full checks

**Files:**
- Delete: whatever no route reaches any more. Find it with `npx tsc -b`, plus a search for imports of every file
  left in `build/`, `home/` and `runs/`. Delete `build/` once it is empty.
- Modify: the user pages under `docs/` that describe the old header, the run sheet or upload-as-input. Follow
  `docs/how-to/development/documentation.md`, and give the data-roots setup one home.
- Modify: `CHANGELOG.md`, with entries under `frontend`, `mendel-api` and `wiener-api`, and `docs/notes/now.md`.

- [ ] **Step 1:** Run `make check`. Expected: PASS.
- [ ] **Step 2:** Run `make guards`. Expected: PASS. If a guard fails, follow the guard-ledger procedure. Never
  loosen a guard to pass.
- [ ] **Step 3:** Run `cd frontend && npx vitest run && npx tsc -b`. Expected: PASS.
- [ ] **Step 4:** Walk `docs/how-to/development/demo-walk.md` again, at both sizes, in light and dark, and compare
  every page with its board file. The demo is ready when the walk passes with no fallback used.
- [ ] **Step 5:** Commit: `docs: the redesigned everyday path (#511)`.
- [ ] **Step 6:** If the walk passed, close #508 and tick the part-1 items on #511.

**→ Final review.**
