# Forge MVP 3a — the shared flow engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the builder's declarative protocol engine out of `mendel-authoring` into a new
pure package, `comeni-flow`, generic over a flow's phases and events, with no change to the
builder's behaviour.

**Architecture:** `comeni-flow` holds `Stage`, `Node[P]`, `Edge[E]`, `Protocol[P, E]` and their
construction checks, the interpreter (`run`, `follow`), forks over a caller-supplied snapshot,
the transition table and the Mermaid export. What was builder-specific in them (`Phase.FAILED`,
`Event.RETRY`, the command set, `MI0216`, the settings snapshot) becomes a field the flow fills
in. `mendel-authoring` keeps its phases, events, commands, settings subjects and `PROTOCOL`,
declared on the core.

**Tech Stack:** Python 3.12, Pydantic 2 generic models.

**Spec:** `docs/superpowers/specs/2026-10-30-forge-3-forging-design.md` §1. Lands before
[plan 3b](2026-10-30-forge-3b-forging.md), possibly as its own pull request.

## Global Constraints

- **No builder behaviour changes.** Every existing test passes; assertions in builder tests are
  not edited (imports may be). The generated diagram is byte-identical:
  `uv run python tools/generate_protocol_doc.py --check` passes with no regeneration.
- `comeni-flow` is pure: on the purity guard's closed list (`tests/support/purity.py`
  `CLOSED_PACKAGES`), importing only the standard library, `pydantic` and `comeni-core`.
- The builder's refusal code stays `MI0216`, still owned by `mendel-authoring`
  (`tests/diagnostics/test_diagnostics_ownership.py`): the code literal lives in
  `mendel_authoring/protocol.py` as `refusal_code="MI0216"`, which that test's `code=` pattern
  matches.
- No re-export shims: importers of the moved names import from `comeni_flow`.

## Review Focus

1. **A flow declaring no failed phase or retry event** (forging has none of the builder's
   retry machinery): construction must not demand them. Test in Task 1.
2. **A second flow's refusal code**: a refusal must carry that flow's code, not `MI0216`. Test
   in Task 2.
3. **Forks with a snapshot type other than the builder's**: the interpreter must not assume
   `.settings`. Test in Task 2.
4. **Generic Pydantic validation**: a `Node` whose phase is not the flow's phase type is refused
   at construction. Test in Task 1.
5. **The builder's `fork_keys()`** still lists exactly the settings it did (shell resolves them).
   Covered by existing builder tests; run them in Task 3.

---

### Task 1: `comeni-flow` with the generic protocol model

**Files:**
- Create: `packages/comeni-flow/pyproject.toml` (modelled on `packages/comeni-vendor/`, deps
  `comeni-core>=0.1.0`, `pydantic>=2.9`), `README.md`, `LICENSE`
- Create: `packages/comeni-flow/src/comeni_flow/__init__.py`, `protocol.py`, `diagram.py`
- Modify: root `pyproject.toml` (workspace dependency + source), `uv.lock` (`uv lock`),
  `packages/mendel-authoring/pyproject.toml` (depend on `comeni-flow`),
  `tests/support/purity.py` (`CLOSED_PACKAGES` gains `comeni-flow`)
- Test: `packages/comeni-flow/tests/test_flow_protocol.py`

**Interfaces:**
- Produces, in `comeni_flow.protocol` (moved from `mendel_authoring.protocol`, behaviour
  identical):
  - `Actor`, `Border`, `Shape` (StrEnums, unchanged values), `Stage` (unchanged).
  - `Node[P]` — fields as today with `phase: P | None`.
  - `Edge[E]` — fields as today with `event: E | None`.
  - `Protocol[P, E]` — today's fields plus `commands: frozenset[str]` (the command set that
    may leave a waiting node), `failed: P | None = None`, `retry: E | None = None`,
    `refusal_code: str`. `_consistent` uses these where it used `Command`, `Phase.FAILED` and
    `Event.RETRY`; the RETRY checks apply only when `retry` is set.
  - Methods unchanged: `fork_keys()`, `exits()`, `transitions()`, `retry_targets()`.
- Produces, in `comeni_flow.diagram`: `to_mermaid(protocol: Protocol) -> str` (moved, output
  byte-identical).
- Produces, in `comeni_flow.forks`: `DEFAULT = "*"` and `Subject[S]` (abstract `title`,
  `options() -> frozenset[str] | None`, `value(snapshot: S) -> str`).

- [ ] **Step 1: Write failing tests** in `test_flow_protocol.py` with a three-node toy flow
  (`class Toy(StrEnum): ASKING, DONE`; `class Go(StrEnum): FINISH`):
  `test_a_flow_without_failed_or_retry_is_valid`;
  `test_a_waiting_node_left_by_a_non_command_is_refused` (`ValueError`, message names the node);
  `test_a_node_whose_phase_is_not_the_flows_type_is_refused` (`ValidationError`);
  `test_transitions_lists_each_event_edge` (`{(Toy.ASKING, Go.FINISH): Toy.DONE}`);
  `test_to_mermaid_draws_each_node`.
- [ ] **Step 2: Run** `uv run pytest packages/comeni-flow -q`. Expected: FAIL (no package).
- [ ] **Step 3: Implement** by moving the generic code out of
  `packages/mendel-authoring/src/mendel_authoring/protocol.py` (lines defining `Actor` …
  `Protocol`, `_validate_forks`, and the Mermaid helpers `_FILL` … `to_mermaid`) into
  `comeni_flow/protocol.py`, `diagram.py` and `forks.py`, generalised as the Interfaces say.
- [ ] **Step 4: Run** the new tests: PASS. `uv lock --check`, `make guards`: PASS.
- [ ] **Step 5: Commit** (`refactor(flow): comeni-flow, the protocol engine made generic (#364)`).

### Task 2: the generic interpreter

**Files:**
- Create: `packages/comeni-flow/src/comeni_flow/interpret.py`
- Test: `packages/comeni-flow/tests/test_flow_interpret.py`

**Interfaces:**
- Produces: `class Refused(ValueError)`; `Ran(at: str, path: list[str])`;
  `follow(protocol: Protocol[P, E], at: str, on: str | None, *, returning_to: P | None = None)
  -> Edge[E]`; `run(protocol, at, command, enter: Callable[[str], str | None], *,
  returning_to: P | None = None, limit: int = 64, snapshot: S | None = None) -> Ran`.
  Behaviour identical to `mendel_authoring.interpret`, except the refusal is
  `coded(protocol.refusal_code, …)` and a fork reads `node.fork.value(snapshot)` with whatever
  `snapshot` the caller passes.

- [ ] **Step 1: Failing tests**: `test_run_rests_where_a_node_waits`;
  `test_a_refusal_carries_the_flows_own_code` (a toy flow with `refusal_code="MD0005"`, a
  declared code unrelated to the builder; `follow` on a missing arrow raises `Refused` whose
  message starts with `MD0005`);
  `test_a_fork_reads_the_callers_snapshot_type` (a `Subject` reading a dataclass snapshot);
  `test_a_cycle_is_refused`.
- [ ] **Step 2: Run**: FAIL.
- [ ] **Step 3: Implement** by moving `interpret.py` from `mendel-authoring`, generalised.
  (`coded()` refuses an undeclared code, which is why the test borrows a declared one.)
- [ ] **Step 4: Run**: PASS.
- [ ] **Step 5: Commit** (`refactor(flow): the interpreter, generic over flow and snapshot`).

### Task 3: the builder declared on `comeni-flow`

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/protocol.py` (keeps the builder's
  node/edge helpers and `PROTOCOL`, now `Protocol[Phase, Event](…, commands=frozenset(c.value
  for c in Command), failed=Phase.FAILED, retry=Event.RETRY, refusal_code="MI0216")`)
- Modify: `packages/mendel-authoring/src/mendel_authoring/forks.py` (keeps `Snapshot`,
  `SettingSubject(Subject[Snapshot])`; imports `DEFAULT`, `Subject` from `comeni_flow.forks`)
- Delete: `packages/mendel-authoring/src/mendel_authoring/interpret.py`
- Modify: every importer of the moved names (17 files; find with
  `grep -rln "from mendel_authoring\.\(protocol\|interpret\|forks\) import" packages tests tools`)
  — import `Actor, Edge, Node, Protocol, Stage` from `comeni_flow.protocol`, `to_mermaid` from
  `comeni_flow.diagram`, `Refused, follow, run` from `comeni_flow.interpret`, `DEFAULT, Subject`
  from `comeni_flow.forks`; `PROTOCOL`, `Snapshot`, `SettingSubject` stay in `mendel_authoring`
- Move: the generic cases of `packages/mendel-authoring/tests/test_interpret.py` and
  `test_protocol.py` that test the engine rather than the builder's flow → `comeni-flow`'s
  tests (assertions unchanged); builder-flow cases stay

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `mendel_authoring.protocol.PROTOCOL: Protocol[Phase, Event]` (same nodes, edges,
  stages, title as today).

- [ ] **Step 1: Baseline**: on the branch before this task, `make test > before.log` and
  `uv run python tools/generate_protocol_doc.py --check`: record pass counts.
- [ ] **Step 2: Implement** the declarations and import changes.
- [ ] **Step 3: Run** `uv run python tools/generate_protocol_doc.py --check`: PASS without
  regenerating (byte-identical diagram). `make test`: the same pass count as Step 1, minus only
  the tests moved to `comeni-flow`, which pass there.
- [ ] **Step 4: Guard evidence**: change one node label in the builder's `PROTOCOL`, run the
  diagram check (FAIL, names the stale page), restore. Record in
  `tests/fixtures/guard-ledger.md` that the diagram guard still bites after the move.
- [ ] **Step 5: Run** `make check` and `make guards`: PASS. Commit
  (`refactor(authoring): the builder's protocol declared on comeni-flow, unchanged`).

### Task 4: records

- [ ] `CHANGELOG.md` (comeni-flow: Added; mendel-authoring: Changed — the engine moved),
  `CLAUDE.md` source map (`packages/comeni-flow/`, and `comeni-flow` in the pure packages
  list of *Boundaries to preserve*), `docs/explanation/` page that describes the protocol
  engine (find with `grep -rl "interpret" docs/explanation`) pointed at `comeni-flow`.
- [ ] `make doc-sizes links`: PASS. Commit (`docs: the flow engine lives in comeni-flow`).
