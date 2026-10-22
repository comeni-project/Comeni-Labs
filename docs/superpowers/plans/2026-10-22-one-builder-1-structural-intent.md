# One builder, plan 1 — structural intent in the engine (A1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person's structural edits — a role switched off, a tool excluded at a site, a port's
source pinned — are intent in the goal that the resolver honours on every re-plan, recorded as
the person's decisions, with conflicts raised and never resolved silently.

**Architecture:** Three new members of `Constraints` (comeni-core) beside `producers`, carried
through `Decisions` (mendel-authoring, pure) and three new decision families (mendel-api, a
subject and a revision table each, like `producer`). The resolver reads them where it already
reads their nearest relative: role absence beside the rule's `presence: absent`, exclusion where
candidates are filtered, a source pin where `_source_for` chooses. A pure `read_edit` turns a
canvas edit into these intents for plan 2 to show and confirm. No UI in this plan.

**Tech Stack:** Python 3.12, pydantic v2, SQLAlchemy + Alembic, pytest.

**Spec:** `docs/superpowers/specs/2026-10-22-one-builder-design.md` (section *Structural hand
edits are intent the engine honours*).

## Global Constraints

- Pure packages (`comeni-core`, `mendel-resolver`, `mendel-authoring`) do no I/O (`make guards`).
- Same goal and recorded decisions in, byte-identical pipeline out; sort every collection before
  it is serialized (invariant 10). **An empty new list is omitted from a dump** (`exclude_if`),
  as `producers` is, so a goal without them dumps the bytes it did.
- Tier 4 stays flagged; a person's override is recorded with `source` person (invariant 6).
- `extra="forbid"` on every new model; typed keys only (the egress guard refuses `Any`, bare
  `str` keys and mappings on anything reachable from `Why`).
- Diagnostics are declared in `packages/comeni-core/src/comeni_core/diagnostics.yml` and raised
  through `coded()`. Routing conflicts take the next free codes in **MD0300–MD0399**.
- No backward compatibility before v0.1.0: `pipeline.yml` moves to **version 8** and only 8 is read.
- Run Python tests through the test database (`make test-db`, then
  `MENDEL_TEST_DATABASE_URL=… uv run pytest …` as `make test` does); never bare against the dev DB.
- Tick each step here as it is done; record deviations at the end.

## Review Focus

1. **An intent that applies nowhere** (its role is filled by nothing, its tool is not a
   candidate at its site, its consumer is not in the plan) must be reported like `inert_pins`,
   not dropped silently. → Task 3, `test_an_intent_that_applies_nowhere_is_reported`.
2. **Excluding the only tool at a needed site** must raise a coded conflict naming the
   exclusion, not an unexplained `UnroutableError`. → Task 3.
3. **Two intents on one subject** (exclude STAR, then pin STAR at the same site): the later
   intent wins and the earlier is retracted in the decision rows, never both applied. → Task 5.
4. **A role absence a wanted output needs** (switch off alignment, still want counts) is a
   coded conflict. → Task 2.
5. **A re-plan after the goal changes** (read length 150 → 50 moves STAR → HISAT2) keeps the
   exclusions and absences, and reports a source pin whose consumer left the plan. → Task 4.

---

### Task 1: The three intents in the goal

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py` (`Constraints`, beside `ProducerPin`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`SCHEMA_VERSION = 8`)
- Test: `packages/comeni-core/tests/test_goal_intents.py` (new)

**Interfaces:**
- Produces:
  - `class RoleAbsence(BaseModel)`: `role: RoleName`
  - `class ProducerExclusion(BaseModel)`: `site: Site`, `contract: ContractId`
  - `class SourcePin(BaseModel)`: `consumer: ContractId`, `port: PortName`, `producer: ContractId`
  - `Constraints.absent_roles: list[RoleAbsence]`, `.exclusions: list[ProducerExclusion]`,
    `.sources: list[SourcePin]` — each `default_factory=list`, `exclude_if` empty
  - `Constraints.excluded_at(site: Site) -> frozenset[ContractId]`
  - `Constraints.source_at(consumer: ContractId, port: PortName) -> SourcePin | None` (last wins)
  - `Constraints.roles_absent() -> frozenset[RoleName]`

- [x] **Step 1: Write the failing tests**

```python
def test_a_goal_without_intents_dumps_the_bytes_it_did():
    goal = Goal.model_validate(example_mapping())
    assert "absent_roles" not in goal.model_dump_json() and "exclusions" not in goal.model_dump_json()

def test_intents_round_trip_sorted():
    c = Constraints(absent_roles=[RoleAbsence(role="trimming")],
                    exclusions=[ProducerExclusion(site=Site(type_id="alignment.bam"), contract="nf-core/star/align@1.11.0")],
                    sources=[SourcePin(consumer="nf-core/subread/featurecounts@2.0.6", port="bam",
                                       producer="nf-core/samtools/sort@1.21.0")])
    assert Constraints.model_validate(c.model_dump(mode="json")) == c

def test_an_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        RoleAbsence(role="trimming", why="x")

def test_the_later_source_pin_wins():
    ...  # two pins at one (consumer, port): source_at returns the second

def test_pipeline_file_version_is_8_and_7_is_refused():
    ...  # a mapping with version: 7 raises the existing version error naming 8
```

- [x] **Step 2: Run them; expect ImportError on the new names.**
  `uv run pytest packages/comeni-core/tests/test_goal_intents.py -v`
- [x] **Step 3: Implement the three models and `Constraints` members**, following `ProducerPin`
  and `producers` exactly (serializer sorting where a set appears; docstrings say whose intent).
  Bump `SCHEMA_VERSION` to 8 and update every test, golden and example that names version 7
  (`rg -l "version: 7"`).
- [x] **Step 4: Run the comeni-core tests, then `make guards`** (the egress guard must accept the
  new types). Expected: PASS.
- [x] **Step 5: Commit** `feat(comeni-core): a goal carries a person's structural intent (A1)`.

### Task 2: A role a person switched off

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py:104-112` (where `absent` is built)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (one new MD03xx code)
- Test: `packages/mendel-resolver/tests/test_person_intents.py` (new; move `resolve_rnaseq`
  from `test_person_pins.py` to `conftest.py` and give it `absent_roles=()`, `exclusions=()`,
  `sources=()` beside `pins=()`, each dumped into `constraints` as `producers` is)

**Interfaces:**
- Consumes: `Constraints.roles_absent()` (Task 1).
- Produces: `IntentConflict(UnroutableError)` in `router.py` carrying `.intent` (the model) and a
  coded message; reused by Tasks 3–4.

- [x] **Step 1: Write the failing tests**

```python
def test_switching_trimming_off_routes_the_reads_straight_to_the_aligner(resolve_rnaseq):
    ir = resolve_rnaseq(absent_roles=[RoleAbsence(role="trimming")])
    assert "trimgalore" not in {n.id for n in ir.nodes}
    assert any(e.from_node not in {"trimgalore"} and e.to_node == "star_align" for e in ir.edges)

def test_switching_off_a_role_the_goal_needs_is_a_coded_conflict(resolve_rnaseq):
    with pytest.raises(IntentConflict, match="MD03"):
        resolve_rnaseq(absent_roles=[RoleAbsence(role="alignment")])
```

- [x] **Step 2: Run; expect FAIL** (unknown keyword / no conflict type).
- [x] **Step 3: Union the goal's absences into `absent`**; when `route()` raises
  `UnroutableError` and an absent role is a person's, re-raise as `IntentConflict` naming it.
  Declare the code (`emitted_by: resolver`, `refuses: true`, a `fix` saying how to turn the role
  back on or drop the wanted output).
- [x] **Step 4: Run; expect PASS.** Also `uv run python tools/generate_diagnostics_doc.py`.
- [x] **Step 5: Commit** `feat(resolver): a role a person switched off is honoured (A1)`.

### Task 3: A tool excluded at a site, and intents that apply nowhere

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py:224-236` (candidate filter),
  `:584-606` (`_choose`, the reason)
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (`inert_intents`, beside `inert_pins`)
- Modify: `diagnostics.yml` (one code for an exclusion leaving no candidate)
- Test: `packages/mendel-resolver/tests/test_person_intents.py`

**Interfaces:**
- Consumes: `Constraints.excluded_at(site)`, `IntentConflict` (Task 2).
- Produces: `inert_intents(ir: PipelineIR, constraints: Constraints) -> list[RoleAbsence | ProducerExclusion | SourcePin]`.

- [x] **Step 1: Write the failing tests**

```python
def test_excluding_star_takes_the_next_aligner_and_says_why(resolve_rnaseq):
    star = _node(resolve_rnaseq(), "star_align")
    ir = resolve_rnaseq(exclusions=[ProducerExclusion(site=star.site, contract=star.contract_id)])
    aligner = next(n for n in ir.nodes if n.site == star.site)
    assert aligner.contract_id != star.contract_id
    assert "you excluded nf-core/star/align@1.11.0" in aligner.why.reason

def test_excluding_the_only_producer_is_a_coded_conflict_naming_it(resolve_rnaseq):
    ...  # exclude samtools sort at its site → IntentConflict, message names the contract

def test_an_intent_that_applies_nowhere_is_reported(resolve_rnaseq):
    ...  # exclusion at an unasked site, absence of a role nothing fills, source pin on an
         # absent consumer: each returned by inert_intents
```

- [x] **Step 2: Run; expect FAIL.**
- [x] **Step 3: Filter `excluded_at(site)` out of `candidates`** before `_choose`; an empty list
  caused by an exclusion raises `IntentConflict`. The next pick keeps the engine's tier, and its
  reason is prefixed `you excluded <contract> here; ` (my call: the person removed a tool, the
  engine still chose the replacement, so the replacement is not the person's choice). Implement
  `inert_intents` as `inert_pins` is.
- [x] **Step 4: Run the resolver tests; expect PASS.**
- [x] **Step 5: Commit** `feat(resolver): a tool a person excluded is honoured (A1)`.

### Task 4: A port's source a person pinned

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py` (`satisfy`: route the pinned
  producer for a pinned port), `resolve.py:233-320` (`_source_for`: the pin selects)
- Modify: `diagnostics.yml` (one code: the pinned producer cannot feed the port)
- Test: `packages/mendel-resolver/tests/test_person_intents.py`

**Interfaces:**
- Consumes: `Constraints.source_at(consumer, port)`.
- Produces: a `SourceDecision` with `human_override` set and `resolved_by="person"` whenever a
  pin decided a port.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_pinned_source_feeds_the_port_and_is_recorded_as_the_persons(resolve_rnaseq):
    ...  # pin featureCounts.bam to the sort's output where a second qualifying source exists
         # (use the HISAT2 path or a two-sorter fixture); assert the edge and a SourceDecision
         # with human_override == "<node>.<port>"

def test_a_pin_whose_producer_cannot_feed_the_port_is_a_coded_conflict(resolve_rnaseq):
    ...  # producer emits the wrong type for the port → IntentConflict

def test_a_re_plan_keeps_intents_and_reports_a_pin_whose_consumer_left(resolve_rnaseq):
    ...  # Review Focus 5: exclusion + source pin on STAR's port; read_length 50 → HISAT2;
         # exclusion still applied; inert_intents names the source pin
```

- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: In `satisfy`, when the consumer's port has a pin, satisfy it through the pinned
  producer** (as a `ProducerPin` at the producer's output site would); in `_source_for`, a pin
  selects among `qualifying` and records the decision; a pinned producer not in `qualifying`
  raises `IntentConflict`.
- [ ] **Step 4: Run all resolver tests; expect PASS. Then `make guards`.**
- [ ] **Step 5: Commit** `feat(resolver): a port's source a person pinned is honoured (A1)`.

### Task 5: The intents as decisions (pure, then stored)

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/decisions.py` (`Decisions`: three lists,
  `goal()`, `from_goal()`)
- Modify: `packages/mendel-api/src/mendel_api/models.py` (six tables, like `PipelineProducer` /
  `PipelineProducerRevision`), `services/decisions.py` (`_FAMILIES`, `_FIELDS`, `import_goal`,
  `read`, and writers below)
- Create: `packages/mendel-api/migrations/versions/<rev>_structural_intents.py`
- Modify: `shape_versions.py` (the new tables at 1), golden shapes (`COMENI_WRITE_GOLDEN=1`)
- Test: `packages/mendel-authoring/tests/test_decisions_intents.py`,
  `packages/mendel-api/tests/authoring/decisions/test_intent_families.py`

**Interfaces:**
- Produces (mendel-api, each with `*, who, actor_kind=ActorKind.PERSON, expected_revision=None`):
  `switch_off_role(draft_id, role)`, `exclude_producer(draft_id, site, contract)`,
  `pin_source(draft_id, consumer, port, producer)`, and `release_intent(draft_id, family, key)`.
  Subject keys: role name; `_site_key(site) + "|" + contract`; `consumer + "|" + port`.

- [ ] **Step 1: Write the failing tests**

```python
def test_decisions_round_trip_the_three_intents():          # pure
    assert Decisions.from_goal(goal).goal(measurements) == goal

def test_a_later_intent_on_one_subject_retracts_the_earlier(db_draft):  # Review Focus 3
    exclude_producer(d, site, STAR, who="ana"); pin_producer(d, site, STAR, who="ana")
    assert goal(d).constraints.excluded_at(site) == frozenset()

def test_each_intent_is_attributed_and_has_history(db_draft):
    ...  # history(draft, subject) names who and when, as for a producer
```

- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** following the `producer` family line for line; a pin and an
  exclusion of the same contract at the same site are one subject in practice: writing one
  retracts the other (`_write(..., action="retract")`).
- [ ] **Step 4: `make test-db`, run the new tests and `packages/mendel-api/tests/infrastructure`
  (shapes, migrations); expect PASS.**
- [ ] **Step 5: Commit** `feat: structural intents are a person's decisions, with history (A1)`.

### Task 6: Reading a canvas edit as intent

**Files:**
- Create: `packages/mendel-authoring/src/mendel_authoring/intent.py`
- Test: `packages/mendel-authoring/tests/test_intent.py`

**Interfaces:**
- Produces: `read_edit(before: DraftGraph, after: DraftGraph, plan: PipelineIR, registry: Registry) -> list[Reading]`
  with `class Reading(BaseModel)`: `kind: Literal["want", "unwant", "pin", "role_absent", "exclude", "source"]`,
  `subject: str`, `said: str` (the engine's sentence, e.g. *"So you never want trimming here — right?"*),
  and `intent: RoleAbsence | ProducerExclusion | SourcePin | ProducerPin | TypeId` — what it would write. Layout-only edits return `[]`. Plan 2 shows `said` and, on
  confirmation, calls Task 5's writers.

- [ ] **Step 1: Write the failing tests**, one per row of the spec's table:

```python
def test_removing_trimgalore_reads_as_trimming_switched_off(): ...
def test_removing_star_reads_as_star_excluded_at_its_site(): ...
def test_removing_the_counts_step_reads_as_no_longer_wanting_counts(): ...
def test_adding_fastqc_reads_as_wanting_qc_from_fastqc(): ...
def test_rewiring_a_port_reads_as_a_source_pin(): ...
def test_swapping_a_tool_reads_as_a_pin(): ...
def test_dragging_reads_as_nothing(): ...
```

- [ ] **Step 2: Run; expect FAIL. Step 3: Implement** — a removed node whose contract fills a
  role every other contract at its site also fills, and whose consumers accept the input
  without it (`state_required_conventional`), is a role absence; a removed node producing a
  wanted type is an unwant; otherwise an exclusion. Order and sort the result.
- [ ] **Step 4: Run; expect PASS. Step 5: Commit** `feat(authoring): a canvas edit is read as intent (A1)`.

### Task 7: Records

- [ ] `docs/reference/` page for `pipeline.yml` (find with `rg -l "producers:" docs/reference`):
  the three constraint lists, version 8.
- [ ] `docs/explanation/invariants.md` only if a claim there changed (verify; do not add prose).
- [ ] `CHANGELOG.md` under comeni-core, mendel-resolver, mendel-authoring, mendel-api.
- [ ] Guard-ledger rows for the conflict and inert tests (each run once against the code with
  its check removed).
- [ ] `make check`, then **`make verify`** (the saved schema and resolution changed; needs Docker
  and Nextflow).
- [ ] Commit `docs: structural intent (A1) — reference, changelog, guard ledger`; tick this plan;
  record the real cost against the estimate in *Deviations*.

## Deviations

(none yet)
