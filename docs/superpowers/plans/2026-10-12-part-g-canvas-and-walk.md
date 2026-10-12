# Part G — Canvas and walk agreement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Execute natively in this session, as required by `CLAUDE.md`; one fresh whole-branch reviewer at the end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canvas, alternative preview, progress and wrap-up describe the same current analysis without extra routine database calls.

**Architecture:** Build an authored canvas frame from already loaded session data and stored provenance. Save alternative snapshots once on the existing proposal row and read them only on preview activation. Derive progress in the existing session read, and keep registry deficiencies separate from run requirements.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy 2, Alembic/PostgreSQL, FastAPI; React 19, TypeScript, TanStack Query 5, Vitest; existing Python-generated HTML artboards.

**Spec:** [Approved design](../specs/2026-10-12-part-g-canvas-and-walk-design.md).
**Status:** Implementation authorized 2026-10-12: “right you can begin implementation”.
**Baseline:** `55f57c21`, branch `stage-four-the-consultant-build`.
**Issues:** #291, #265, #266, #294; assigned canvas/walk and Dev mode items in #268. Parent #284.

## Global Constraints

- **Preview — not applied** temporarily replaces the canvas with the complete alternative.
- Progress adds no database queries or polling; no per-node/alternative/history N+1 reads.
- Snapshot maps are saved once in a nullable, deferred column on the existing proposal row.
- Routine SQL and public pending/history responses omit snapshots; GET never writes.
- Preview does not re-resolve, call a model, run gates or mutate decisions/reviews.
- Context includes draft revision, decision revision, session version, registry and proposal id.
- Tier 4 stays flagged after approval; review applicability is a separate presentation.
- **To run, provide…** lists actual inputs and intentionally deferred settings.
- Dev mode adds technical detail and extra gap stops; an existing run blocker stays visible.
- No new decision tables, bulk backfill, undo, DE extraction or Part H readiness changes.
- Generated clients/protocol documents are regenerated; tests never call a live model.
- Database tests/upgrade rehearsals use named throwaway databases, never configured dev data.
- Tick tasks/steps after evidence; record deviations, observed RED→GREEN and commits below.
- If effort exceeds the current estimate by about double, stop and explain the change promptly.

## Review Focus

1. A preview request from another session must not reveal that session's proposal (Task 3).
2. Leaving and re-entering a failed preview must not silently retry it (Task 8).
3. A stale/unbuildable projection must not be presented as current after a successful preview (Tasks 4, 8).
4. Manual edits sharing old node ids must not recover stale resolver provenance (Tasks 4, 7).
5. Mixed pointer/focus events must not cancel a pinned touch preview or steal focus (Task 8).

## File map and interfaces

Existing paths were inspected. New paths below are intentional additions, not claims
that these types already exist. Keep new files focused; do not split unrelated code.

| Responsibility | Home |
|---|---|
| Frozen frame/snapshot transport types | New `packages/mendel-api/src/mendel_api/authoring/canvas.py` |
| In-memory authored/manual frame adapter | New `packages/mendel-api/src/mendel_api/services/authoring_canvas.py` |
| Snapshot read/context refusal | New `packages/mendel-api/src/mendel_api/services/authoring_preview.py` |
| Snapshot writes | Existing `stages/building/cards.py` and `PipelineAuthoringProposal` |
| Current/historical progress | New pure `packages/mendel-authoring/src/mendel_authoring/progress.py`; existing envelopes/read model |
| Wrap-up classification | Existing `mendel_authoring/wrapup.py`, `plan.py`, building `walk.py` |
| Complete-frame rendering | Existing living builder/surface/canvas/node/reducer |
| Preview lifecycle/cache | New `frontend/src/build/living/useAlternativePreview.ts`; existing step card |

Contracts to define in the owning tasks:

```python
# Task 2: authoring/canvas.py; reuse existing OfferContext and view DTOs.
class CanvasFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    context: OfferContext
    proposal_id: str | None
    current: bool
    graph: DraftGraph
    steps: list[StepView]
    channels: list[ChannelView]
    placement: dict[str, dict[str, int]]

class AlternativePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    option_id: str
    contract: str
    frame: CanvasFrame
    observed_context: OfferContext

# Task 5: progress.py; position is 1-based and absent when no step is offered.
class OfferProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    position: int = Field(ge=1)
    total: int = Field(ge=1)
    again: bool = False

class WalkProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reviewed: int = Field(ge=0)
    total: int = Field(ge=0)
    active: OfferProgress | None = None
```

Validate `position <= total`, `reviewed <= total`, unique graph/step identities,
step metadata matching graph contracts, and placement/channel endpoints belonging
to the frame. Null frames are allowed before anything exists. Do not put the
private blueprint or snapshot map into `CanvasFrame`.

The saved frame's context is its original offer context. `observed_context` in
a preview response is the current context checked by that GET, not a rewrite of
the saved frame. The offer-creation dispatcher can advance `row_version` after
the snapshot is constructed: compare the caller's expected session version with
the current row, while comparing saved offer freshness by proposal identity,
draft revision, decision revision and registry. Do not demand equality between
the original session version and a later valid read's session version.

## Verification commands and baseline safety

Use Python 3.12 as in Part F. Before running database tests, point *all* Mendel
test/CLI URLs at the throwaway. The Makefile reads `.env`; pass overrides to Make
as well as exporting them. Do not print `.env` or other credentials.

```bash
export MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel
export MENDEL_TEST_DATABASE_URL=$MENDEL_DATABASE_URL
export WIENER_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener
export WIENER_DATABASE_URL=$WIENER_TEST_DATABASE_URL
export COMENI_REQUIRE_DB=1
make test-db
uv run pytest packages/mendel-authoring/tests packages/mendel-api/tests/test_authoring_building.py packages/mendel-api/tests/test_authoring_routes.py -q
```

After each task run its focused guards, then its affected suite once. At completion
run `make check guards`, frontend Vitest and `npx tsc -b`; run `make verify` instead
if execution touches a file listed in `CLAUDE.md`'s mandatory real-tool trigger.
Part G intends no resolver/compiler/artifact semantic changes. Report #303's known
Python 3.14 inspection failure and #296 separately; do not spend G fixing them.

## Task 1 — Establish evidence and update the affected artboards

**Files:** Read `tests/README.md`, `docs/internals/walking.md`, Part F's execution
record and guard ledger. Modify `.design/living-pipeline/build_living.py`, its
`README.md` and generated affected boards. Create test support
`packages/mendel-api/tests/part_g_setup.py`; extend that package's `conftest.py`
only for the `g_case` fixture. No frontend product changes yet.

**Interfaces:** Define `Case(session_id, proposal_id, option_id, goal, context)` as
a frozen test dataclass. `at_aligner(pacing="together") -> Case` creates a session
through the same calls as `_resolving` in `test_authoring_building.py`, accepts
preceding proposals with `commands.SettleStep`, and selects HISAT2's offered option
by its exact contract `nf-core/hisat2/align@2.2.2`. `g_case` yields this case under
the existing authoring table cleanup pattern. No production imports of test setup.

```python
@dataclass(frozen=True)
class Case:
    session_id: str
    proposal_id: str
    option_id: str
    goal: Goal
    context: OfferContext  # Current context from the session read, not pre-commit offer version.
```

- [x] Record branch/HEAD, registry SHA, database heads and existing changes in the
  execution record. Capture baseline session SQL counts with SQLAlchemy's
  `before_cursor_execute`, excluding fixture setup; save SQL text, never parameters.
- [x] Add the reusable case and SQL-capture context manager. Assert proposal and
  option collections are non-empty before selecting. Confirm the shared helper
  works by driving the existing STAR→HISAT2 building guard through it.
- [x] Reproduce the reported canvas issues in an isolated recorded-evidence browser
  session; collect them in one walk, without patching between findings. Store
  screenshots/API assertions locally under `build/part-g-review/`. Any newly found
  defect gets an issue before a fix, as the repository requires.
- [x] Update `board_choose` to show only the complete HISAT2 alternative and its
  **Preview — not applied** banner/close control. Show loading/error, re-review,
  separated run requirements/gaps and developer detail in affected boards.
  Replace the older intrinsic/asserted preview explanation in the design README.
- [x] Generate/render and inspect the boards before touching React:

```bash
python3 .design/living-pipeline/build_living.py
python3 .design/_prev.py --dir living-pipeline --glob 'Living*'
make links doc-sizes
```

Inspect both wide and narrow renders, including the generator's 900px pass;
record which images were viewed. Commit artboards/test support as the first
checkpoint. This task establishes evidence; it does not claim the defects fixed.

## Task 2 — Retain complete alternatives and store deferred snapshots

**Files:** Modify `mendel_authoring/alternatives.py`, API `authoring/envelopes.py`,
`models.py`, `stages/building/cards.py`. Create the frame types above and migration
`packages/mendel-api/migrations/versions/b9d3e7f5c164_proposal_preview_views.py`
off current head `a8c2d6e4b053`. Tests: pure `test_amendments.py`, API `test_models.py`,
`test_migrations.py`, new `test_authoring_preview.py`.

**Interfaces:** `Alternative.blueprint: Blueprint | None = None` retains the
already resolved candidate. `StepOffer.preview_options: list[str] = []` announces
saved options. `preview_frames(blueprint: Blueprint, context: OfferContext,
proposal_id: str, layers) -> CanvasFrame` constructs a full read-only view in the
new canvas adapter; Task 4 extends that adapter with the partial live-frame path.
Store `dict[str, AlternativePreview]` serialized in `proposal.preview_views`.
For a saved snapshot set `observed_context` to the offer context; the GET returns
a new response wrapper with the context it checked, leaving stored JSON intact.

- [x] Add a pure guard proving one candidate resolve call produces both its diff
  and retained blueprint; add the refusing/inert candidate cases:

```python
def test_alternative_retains_the_same_resolved_blueprint(blueprint_of):
    before = blueprint_of(STAR_BP, {"star_align": ALIGNMENT})
    after = blueprint_of(HISAT2_BP)
    calls = []
    def resolve(goal):
        calls.append(goal)
        return after
    options = alternatives_of(before, Goal(), "star_align",
                              [HISAT2_BP["hisat2_align"]], resolve, (Unroutable,))
    assert len(options) == 1 and len(calls) == 1
    assert options[0].blueprint == after
    assert options[0].diff.added == ["hisat2_build", "hisat2_align"]
```

Use existing `STAR_BP`, `HISAT2_BP`, `ALIGNMENT`, `Unroutable` fixtures/constants from
`test_amendments.py`. Add database guards for null old rows, typed map/context
validation and routine ORM reads omitting the column. Watch the missing snapshot
behavior fail before adding the implementation.
- [x] Run the focused test and record its exact assertion failure in the ledger;
  do not count an import error as the defect's RED.
- [x] Retain the candidate once and construct its full frame from the actual
  resolved result. Wire snapshot creation into `cards.offer`, generating the
  proposal id/context before constructing snapshots. Preserve existing options,
  amendments and offered wires; no additional resolver pass.

For the complete view, project all blueprint nodes into an in-memory graph with
the existing pure `committed` helper, starting with empty graph/provenance and
the blueprint profile. This is a view conversion only: no database review is
created and every preview node is presented as proposed. Preserve module/setting
provenance in metadata; preview conversion must not fabricate a person approval.

```python
preview_views: Mapped[dict | None] = mapped_column(
    JSON, nullable=True, deferred=True, deferred_raiseload=True,
)
# Migration upgrade, no UPDATE/backfill/default:
op.add_column("pipeline_authoring_proposal", sa.Column("preview_views", sa.JSON(), nullable=True))
```

Validate map keys, option/contract/context consistency before the existing offer
write. Exclude refused alternatives. Migration downgrade follows the repository's
restore-backup convention; do not discard retained view history implicitly.
- [x] Upgrade only the throwaway test database; run focused guards and migration
  parity. Test an older null snapshot row and compile default proposal SELECT to
  assert `preview_views` is absent. Confirm ordinary attribute access raises rather
  than lazy-loading. Record GREEN and commit citing #265/#291.

## Task 3 — Serve one saved preview with strict context checks

**Files:** Create `services/authoring_preview.py`; modify `routes/authoring.py`.
Tests: new `packages/mendel-api/tests/test_authoring_preview.py` and existing
`test_authoring_routes.py`. Regenerate the API client after the route is added.

**Interfaces:** `read(session_id: str, proposal_id: str, option_id: str,
expected: OfferContext) -> AlternativePreview`. Endpoint:
`GET /pipeline/authoring/{session_id}/proposals/{proposal_id}/alternatives/{option_id}`,
with required query parameters `expected_revision`, `expected_decision_revision`,
`expected_session_version`, `expected_registry`. Return the Task 2 DTO.

- [ ] Add service/HTTP guards for correct STAR→HISAT2 graph/ports/wires, session
  ownership, unknown/refused options, settled/stale offers, registry movement and
  mismatches in each current context field. Add a regression for the dispatcher
  advancing the version after offer creation: the fresh pending offer remains
  previewable with the current read's context. Example using Task 1's fixture:

```python
def test_preview_read_returns_saved_alternative_without_changing_state(g_case):
    before = facade.read(g_case.session_id)
    got = authoring_preview.read(g_case.session_id, g_case.proposal_id,
                                g_case.option_id, g_case.context)
    ids = {node.id for node in got.frame.graph.nodes}
    assert {"hisat2_build", "hisat2_align"} <= ids
    assert not {"star_genomegenerate", "star_align"} & ids
    assert facade.read(g_case.session_id) == before
    assert got.observed_context == g_case.context
```

Also replace goal resolution/model/gate seams with functions raising if invoked,
capture SQL for the preview read, and assert no INSERT/UPDATE/DELETE. Cross-session
lookup is 404 even if the option id is valid. Old null maps say unavailable and
do not prevent accepting the original card. Watch the new behavior's RED.
- [ ] Implement a single joined SELECT of proposal/session/draft and the explicitly
  requested column in one read transaction. Check ownership before returning data,
  then pending state, current/expected context and selected option. Do not acquire
  mutation locks or mark a proposal stale on GET. Reuse `coded()` refusal vocabulary.

```python
stmt = (select(PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft)
        .join(PipelineAuthoringSession,
              PipelineAuthoringProposal.session_id == PipelineAuthoringSession.id)
        .join(PipelineDraft, PipelineAuthoringSession.draft_id == PipelineDraft.id)
        .options(undefer(PipelineAuthoringProposal.preview_views))
        .where(PipelineAuthoringProposal.id == proposal_id,
               PipelineAuthoringSession.id == session_id))
```

Validate the saved map and expected context inside the transaction. Use the
existing registry digest machinery; no new scan/network/model dependency.
  Check current context independently of the saved frame's historical session
  version as defined above; return current `observed_context` in the wrapper.
- [ ] Return the coded API refusal as an inline preview error. If a distinct
  unavailable diagnostic is needed, declare it in `comeni_core/diagnostics.yml`
  and regenerate its reference; do not reuse a misleading code or embed raw strings.
- [ ] Run preview service/routes tests, migration guards, `make client`, and frontend
  TypeScript. Confirm exactly one preview SELECT and no snapshot material on session
  HTTP/history reads. Commit the endpoint checkpoint.

## Task 4 — Build an authoritative live canvas frame from loaded data

**Files:** Extend new `services/authoring_canvas.py`; modify `services/build.py`
only to share port/channel formatting, `services/session.py`, `routes/authoring.py`.
Tests: new `packages/mendel-api/tests/test_authoring_canvas.py`; existing building,
build-service and keep tests. Reuse existing registry/channel materialisation helpers.

**Interfaces:** `frame_of(*, blueprint: Blueprint | None, graph: DraftGraph,
provenance: DraftProvenance, pending: StepOffer | None, proposal_id: str | None,
context: OfferContext, current: bool, ownership: str, placement: dict, layers)
-> CanvasFrame | None`. It accepts values, not ORM rows or a Session. The session
response adds `canvas: CanvasFrame | None` using values already loaded.

- [ ] Write guards for pending upstream wiring in both pacing modes, existing-node
  uniqueness, full edge-key uniqueness and current recorded tiers. Example:

```python
def test_pending_aligner_uses_its_upstream_index(g_case):
    frame = facade.read(g_case.session_id)["canvas"]
    ids = [node["id"] for node in frame["graph"]["nodes"]]
    assert len(ids) == len(set(ids))
    assert any(e["from_node"] == "star_genomegenerate" and e["to_node"] == "star_align"
               for e in frame["graph"]["edges"])
    assert not any(c["type_id"] == "genome.index.star" for c in frame["channels"])
```

Add grouped inputs, same-type/different-state channels, sample/run scope and count;
manual recorded provenance versus unrecorded tier-4 fallback; stale projection
after unbuildable correction; no future-node metadata in ordinary frames. Watch RED.
- [ ] Build the visible graph from the stored graph plus the compatible pending
  node/edges. Read metadata from the corresponding blueprint steps and provenance.
  Share formatting helpers with `build._view` without routing authored views through
  its unrecorded-manual fallback. Compute entry channels with the actual wiring
  and grouping; keep the existing server placement for authored steps. Full preview
  frames use the same formatter on the complete alternate blueprint.

```python
edge_key = lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)
visible = {node.id: node for node in graph.nodes}
if pending is not None and pending.node not in visible:
    visible[pending.node] = DraftNode(id=pending.node,
                                     contract_id=pending.block.contract, params=[])
edges = {edge_key(e): e for e in [*graph.edges, *(pending.edges if pending else [])]
         if e.from_node in visible and e.to_node in visible}
drawn = graph.model_copy(update={"nodes": list(visible.values()), "edges": list(edges.values())})
```

Import the existing `DraftNode` from `comeni_core.plan.draft`. Its empty override
list means no new override; settings/tiers displayed come from the stored step
metadata rather than from re-resolving that node. If a pending node already exists,
validate its contract before adding any offered edges.

For manual mode pass stored provenance to existing materialisation. When a node's
contract differs from the blueprint, use its matching stored provenance; never
restore a stale blueprint decision solely because the id is equal.
- [ ] Attach the frame in `session.read` before leaving the existing scope. Pass
  already loaded values into the adapter; no `decisions.read/reviews` call per node
  and no separate DB context. Preserve existing response fields for other callers.
- [ ] Compare observed SELECT count with Task 1 baseline; assert no added queries,
  no snapshot column loaded and no resolver/model/gate call during authored reads.
  Extend schema/client, run focused guards plus keep/materialisation regressions,
  record GREEN and commit #266/#268/#294.

## Task 5 — Carry current progress and fixed historical positions

**Files:** Create pure `mendel_authoring/progress.py` and `tests/test_progress.py`.
Modify API `authoring/envelopes.py`, `stages/building/cards.py`, `services/session.py`,
`services/decisions.py`, `stages/building/walk.py`, `routes/authoring.py`; test
`test_authoring_canvas.py` and `test_authoring_building.py`.

**Interfaces:** `progress_of(order: list[str], retained: frozenset[str],
previously_reviewed: frozenset[str], pending: str | None) -> WalkProgress`.
`StepOffer.progress: OfferProgress | None = None` stores original offer context.
Session response `progress: WalkProgress | None` is absent for manual ownership.
History exposes the original offer's progress through its envelope, with legacy
null/default preserved.
Add `ReviewState(retained: list[Reviewed], previously_reviewed: frozenset[str])`
and `decisions.review_state(draft_id) -> ReviewState`, reusing the exact `_current`
review query that `decisions.reviews` already executes. `reviews` delegates and
returns its `retained` list. Do not add a second historical-review query.

- [ ] Write pure guards for first offer, swap insertion, removed nodes, same-node
  re-review, duplicate historic reviews, complete/empty plan and pending node absent
  from order. Add an API guard preserving original offer position after a swap:

```python
def test_re_review_uses_current_position_not_lifetime_proposals():
    got = progress_of(["index", "align", "counts"], frozenset({"index"}),
                      frozenset({"index", "align", "old_index"}), "align")
    assert got.reviewed == 1 and got.total == 3
    assert got.active == OfferProgress(position=2, total=3, again=True)
```

Watch position/total guard fail against historical-count behavior.
- [ ] Implement current position by `order.index(pending) + 1`; retained count uses
  unique current nodes only. `again` requires a prior review of that current node.
  Invalid pending identity is refused, never clamped to a plausible number. Validate
  ordinal/count bounds. Preserve removed/superseded historical entries.

```python
active = None if pending is None else OfferProgress(
    position=order.index(pending) + 1, total=len(order),
    again=pending in previously_reviewed,
)
return WalkProgress(reviewed=len(set(order) & retained), total=len(order), active=active)
```
- [ ] Feed the function from the latest review rows already loaded in `session.read`,
  reducing by node in sequence order. For offer creation use review data already
  computed by building `step`: obtain both retained reviews and historical node
  identities through `review_state`, then pass them to `cards.offer` instead of
  fetching again. Extend `cards.offer(..., *, retained: list[Reviewed],
  previously_reviewed: frozenset[str])` and update its building callers.
  Stamp original progress in new offers. Legacy history without it shows no ordinal.
- [ ] Run pure/API guards, prove SQL count unchanged, regenerate client, record GREEN
  and commit the progress checkpoint. No historical data rewrite or extra endpoint.

## Task 6 — Separate registry deficiencies and make Dev mode truthful

**Files:** Modify pure `wrapup.py`, `plan.py` and their tests; API building `walk.py`,
`authoring/types.py`; `comeni_core/settings/catalogue.py`, existing developer setting
tests/golden menu; `mendel_authoring/protocol.py`, `docs/design/authoring-protocol.md`.
Tests: API `test_authoring_building.py`, `test_build_plan.py`.

**Interfaces:** Keep `WrapUp.inputs` and `unset` (legitimate run-time settings), add
`gaps: list[Gap]`. `wrap_up` derives all three from existing pipeline/decision data.
Session adds `show_gap_details: bool` from the recorded policy; new step blocks add
`unresolved_settings: list[str] = []` for user-facing explanation independent of
technical `Gap.fix` paths. Frame/run diagnostics remain the existing authority.

- [ ] Extend the real-registry guard: HISAT2's null/no-domain `seq_platform` belongs
  in gaps, not `unset`. Preserve pure fixture strandedness as a legitimate deferred
  setting. Add a receipt assertion and Dev on/off pacing precedence cases:

```python
def test_domain_gap_is_not_a_run_requirement(g_case):
    alternate, _ = bp.resolve(ChooseTool(pin=ProducerPin(
        site=Site(type_id="alignment.bam"), contract=HISAT2)).apply(g_case.goal))
    wrap = wrap_up(alternate, declared.of(registry.stack()))
    assert "hisat2_align.seq_platform" not in wrap.unset
    assert any(g.subject == "seq_platform" for g in wrap.gaps)
```

Resolve only in test setup, not reads/preview. Use the actual alignment site from
the candidate amendment if it carries required states; preserve canonical Site.
Watch receipt misclassification fail before implementation.
- [ ] Collect no-domain decision keys with `gaps.no_domain`; subtract only those
  from unset settings, retain true input channels, and deduplicate typed gaps.
  Build **To run, provide…** and **Registry information is incomplete** separately.
  Set plain-language unresolved-setting data without exposing repository paths.

```python
domain_gaps = {record.key for record in pipeline.decisions if no_domain(record)}
unset = [f"{step.id}.{setting.name}" for step in pipeline.steps for setting in step.settings
         if setting.value is None and f"{step.id}.{setting.name}" not in domain_gaps]
gaps = [gap for step in pipeline.steps for gap in gaps_of(step, pipeline, declared)]
```
- [ ] Use the stored `show_gaps` policy for developer details. Existing diagnostic
  refusals keep run disabled/explained regardless of Dev mode. Do not invent a
  `blocking=True` rule for all gaps or add another run gate. Keep need → gap →
  together pacing precedence. Update help text/comments and protocol generator.
- [ ] Run wrap-up/needs/stage-four/settings/building guards; regenerate settings
  golden output through its existing fixture workflow and protocol/reference docs:

```bash
uv run pytest packages/mendel-authoring/tests/test_wrapup.py packages/mendel-authoring/tests/test_needs.py packages/mendel-authoring/tests/test_stage_four.py packages/comeni-core/tests/test_settings_developer.py packages/mendel-api/tests/test_build_plan.py -q
uv run python tools/generate_protocol_doc.py
make client docs links
```

Record GREEN and commit the typed classification/Dev mode checkpoint.

## Task 7 — Render the coherent frame, progress and gap visibility

**Files:** Modify living `LivingBuilder.tsx`, `LivingSurface.tsx`, `LivingCanvas.tsx`,
`LivingNode.tsx`, `DecisionLog.tsx`, `format.ts`, `authoringReducer.ts`,
`blocks/StepProposalCard.tsx`, fixtures `fake.ts`/`guided.ts`. Extend existing
surface/reducer/conversation/step-card/collection/replay tests; create
`frontend/src/build/living/LivingBuilder.test.tsx` for the live route and
`format.test.ts` for progress copy.

**Interfaces:** `LivingSurface` consumes the session's `canvas` frame; tests/fake
routes construct coherent local frames. `progressWords` reads `session.progress`.
Step cards receive fixed `OfferProgress | null` and `showGapDetails: boolean`.
Node receives `reviewState: "reviewed" | "again" | "proposed" | "unknown"`.

- [ ] Write guards for duplicate node, no false sources, real recorded tier, re-review
  copy and stable historical positions. Mock the live session response and assert
  no `/pipeline/draw` request and no fabricated footer while a mutation is pending:

```tsx
it("uses the session frame without asking the manual draw endpoint", async () => {
  // Use this file's route + QueryClient harness and a recorded coherent session.
  await screen.findByTestId("living-node-star_align");
  expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/pipeline/draw"))).toBe(false);
  expect(screen.queryByText("0 settled")).toBeNull();
});
```

Also test stale projection label/run disable, manual same-id different contract,
true INPUT boxes, grouped collection rendering, Dev-off warning without paths and
Dev-on detail. Preserve existing FactHistory refresh/correction guards. Watch RED.
- [ ] Remove live `useDrawn`; consume matching graph/metadata/channels from the frame.
  Keep last complete frame during mutation with a working indicator; stop using
  optimistic graph insertion in the living canvas. Initial/no-frame states are
  explicit. Keep manual builder edits and RunSheet using the actual draft's graph,
  never preview metadata. Deduplicate even when fixtures re-offer an existing node.
- [ ] Replace transcript-count numbering with current `progress.active` and historical
  envelope progress. Render **Review step … again**, **… steps reviewed** and legacy
  node-only history. Add review text without repainting recorded tier colour. Gate
  technical gap paths by `showGapDetails`; plain unresolved-setting copy remains.
- [ ] Update fake/guided fixtures to coherent frames/progress so they exercise the
  same renderer rather than retaining label-only preview behavior. Run focused
  Vitest, collection/replay/correction tests and `npx tsc -b`. Compare screenshots
  with Task 1 artboards; record GREEN and commit the normal-canvas UI checkpoint.

## Task 8 — Add complete preview interaction with a bounded cache

**Files:** Create `useAlternativePreview.ts` and its test beside it. Modify living
`LivingSurface.tsx`, `LivingCanvas.tsx`, `blocks/StepProposalCard.tsx`, reducer and
conversation tests, and `fake.ts`/`guided.ts` with saved full preview fixtures;
add `AlternativePreview.test.tsx` for surface integration.
Use generated API types; remove obsolete `instead` label substitution props.

**Interfaces:** `PreviewSelection = { option: string; pinned: boolean } | null`.
`useAlternativePreview(session, selection)` returns matching snapshot, loading,
error and explicit `retry()`. Step-card callback is
`onPreview(option: string | null, mode: "temporary" | "pinned")`. Cache key:
`["alternative-preview", session.id, proposal.id, option, draftRevision,
decisionRevision, sessionVersion, registry]`.

- [ ] Write request-count guards: first activation fetches once; repeated hover,
  focus, pin and reopen of the same context do not fetch again. Test a failed read,
  close/reopen, then deliberate Retry; test delayed option A after selecting B and
  delayed result after a context change. Watch RED before wiring the hook.
- [ ] Implement the context-bound query and deliberately disable automatic triggers:

```tsx
useQuery({
  queryKey: previewKey,
  queryFn: () => get<AlternativePreview>(previewPath),
  enabled: (query) => available && selected && query.state.status !== "error",
  staleTime: Infinity,
  gcTime: Infinity,
  retry: false,
  retryOnMount: false,
  refetchOnMount: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  refetchInterval: false,
});
```

Build `previewKey`/`previewPath` from the exact Task 3 endpoint/context; add no
polling. Here `available`/`selected` are booleans derived from the pending offer and
selection. The query's error cache disables reactivation until explicit `retry()`
or context changes. Explicit Retry uses `refetch` on the
same key. Remove cache entries for superseded proposals and session unmount so
`gcTime: Infinity` cannot accumulate old-session snapshots indefinitely. Multiple
events requesting the same key share the QueryClient request.
- [ ] Keep the current build canvas mounted but hidden/inert during a successful
  preview, preserving its viewport/drag positions/selection. Mount a separate
  read-only preview canvas with real node ids and all nodes marked proposed;
  disable drag/edit tools and do not pass committed animation events. Add banner,
  Close/Escape and touch toggle; restore focus to its explicit trigger on close.
  Temporary hover/focus cannot clear an existing pinned selection.
- [ ] Render loading/error beside the still-visible build; old unavailable/refused
  options cannot fetch or apply. Disable Keep/Run while a full preview is shown;
  the original card's **Change it** still uses its checked offer. Clear selection
  on proposal/context/session change, including transition to no pending proposal.
  Reject late snapshots unless `observed_context` exactly matches the active cache
  key/context; the immutable frame's original offer version is not the current
  session-version check. Never change the saved frame in the cache to make it match.
- [ ] Prove mouse/keyboard/touch behavior, pinned-preview mixed events, Escape focus,
  viewport restoration, preview edit/run prohibition, acceptance, stale-projection
  warning and retry counts through integration guards. Run focused Vitest and
  TypeScript, inspect wide/narrow screenshots and console, record GREEN and commit
  #265's full preview checkpoint.

## Task 9 — Verify the complete walk, review once and close the scoped work

**Files:** Update guard ledger, `docs/notes/now.md`, journal and protocol/design
records; create `docs/notes/research/2026-10-12-part-g-execution.md`. Archive approved
plan/spec only when complete. Local screenshots/results stay in ignored
`build/part-g-review/`. Issue mutations follow the repository's explicit walk workflow.

- [ ] Drive real API/React against a freshly named throwaway database at both heads,
  with recorded model/inspection replies: preview STAR→HISAT2, close, accept, complete,
  correct read length, re-review dependency chain, reload, stale two-tab mutation,
  unavailable legacy preview and manual fork. Exercise both pacing and Dev modes.
  Assert API/canvas agreement and no duplicate React keys; inspect screenshots.
- [ ] Capture network and SQL evidence: no normal draw request or extra polling,
  session SELECT count no higher than Task 1 baseline, snapshot column absent from
  routine SQL/history, one preview read per cached context and no writes/re-resolution.
  Compare one-node and multi-node/history cases to catch N+1 growth. Run null-old-row
  upgrade and Alembic parity on the throwaway; do not upgrade actual dev data.
- [ ] Run one full affected verification after focused guards pass:

```bash
make check guards MENDEL_DATABASE_URL="$MENDEL_DATABASE_URL" WIENER_DATABASE_URL="$WIENER_DATABASE_URL"
cd frontend
npx vitest run
npx tsc -b
```

If mandatory resolver/compiler/artifact files changed, use `make verify` with the
same overrides. Record actual test counts, skipped tests and baseline failures;
do not repeat broad suites absent changes/failures. Rebuild changed baked app
images once at the end without starting/upgrading the real development stack.
- [ ] Dispatch exactly one fresh native whole-branch review over this plan's baseline
  through implementation HEAD, giving the approved spec, evidence and query limits.
  Use the executing-plans review procedure and most capable available model. Work
  remains native; no implementer agents. Address material findings in one grouped
  test-first fix pass, rerun affected checks, and record any remaining findings.
- [ ] Mark only assigned #268 items fixed; close #265/#266/#294/#291 with commits and
  observed failing guards, update #284 to Part H next. Leave undo/DE/model-variance
  and unrelated findings open. Record completion/limits, compact the journal,
  archive plan/spec, and run documentation/link/path/size checks. Keep the requested
  local branch; do not push, merge or deploy without a later instruction.

## Coverage and execution record

| Spec requirement | Task |
|---|---|
| Coherent authored/manual view, wiring, uniqueness, provenance | 2, 4, 7 |
| Complete preview, frozen context, old offers, stale/refused reads | 2, 3, 8 |
| Current and historical progress, re-review | 5, 7 |
| Registry deficiencies, run settings and Dev mode | 6, 7 |
| No extra SQL/polling, snapshots excluded, bounded cache | 1, 2, 3, 4, 5, 8, 9 |
| Loading, manual/stale projection, preview isolation | 4, 7, 8 |
| Artboard, browser, tests, migration, review and closure | 1, 9 |

During execution append per-task commits, observed RED→GREEN guards, query counts,
images inspected, actual checks and rulings here. At plan-writing time no tasks
have been executed and no product files have changed.

Implementation references: [SQLAlchemy deferred columns and raiseload](https://docs.sqlalchemy.org/en/20/orm/queryguide/columns.html),
[TanStack Query options](https://tanstack.com/query/latest/docs/framework/react/reference/useQuery).
