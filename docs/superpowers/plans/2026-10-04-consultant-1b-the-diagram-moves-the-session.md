# Consultant 1b — the diagram moves the session — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every authoring session stores the node it rests on (`at`). Every move it makes is an arrow of the protocol, taken by a named command or a handler's outcome, through one dispatcher that runs the core's interpreter. No hand-written phase change is left in the shell, and everything a person sees behaves as before.

**Architecture:** The protocol (`mendel_authoring.protocol`) marks every built node as acting, waiting or passing straight through, and names every arrow a session can take. The shell gains:
- `mendel_api/services/session.py`: the dispatcher. It reads `at`, runs `interpret.run` with the shell's handlers, and writes `at` and the phase read off the node, compare-and-swap.
- `mendel_api/stages/`: one module per section, each acting node's handler registered with `@handles`.

Today's service functions (`answer_gap`, `decide_goal`, `settle_step`, `start_building`, `retry`, `say`, `offer_next_gap`, `answer_with_sample`, `answer_with_reading`) stay the public entry points, so the routes, the jobs and the existing tests do not change. Each now:
1. checks its own payload;
2. asks the diagram whether its command is legal from where the session rests;
3. records what the person decided;
4. performs the command.

The handlers are thin and call the code that already exists. Plan 1c moves that code into the stage modules behind the facade, in one transaction per command.

**Tech Stack:** Python 3.12, pydantic 2, SQLAlchemy 2, Alembic, pytest, Postgres (`127.0.0.1:5442`).

**Spec:** `docs/superpowers/specs/2026-10-04-the-consultant-build-design.md` §3.2, §8, §9, §10 (part 14.7.8.1). It follows `docs/superpowers/plans/2026-10-04-consultant-1a-the-core.md` (landed, `539ca025`). Issue #136.

## Global Constraints

- **`mendel-authoring` never imports `mendel-api`, FastAPI, SQLAlchemy, ARQ, a model client, or anything that reaches the network** (spec §3.1). Everything in the shell may import it.
- **Behaviour unchanged** (spec §10): the existing suite passes untouched. The only exceptions are tests of the protocol's own shape, which this plan names: `test_protocol.py`, `test_interpret.py`, `test_the_core.py`.
- **A command with no arrow from where the session rests is refused with MI0216**, naming the node and the command (spec §8).
- **A job's completion for a session that moved on is ignored**: its command has no arrow from where the session now is (spec §8).
- **Every session's `at` is a built node** (spec §9).
- Python tests always run with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` on the command line, from the repository root. Never bare pytest.
- Run `make check` on its own before each commit and read make's own exit code. Run `make verify` after the migration task.
- Guards are watched failing and recorded in `tests/fixtures/guard-ledger.md`.
- Diagnostics come from `comeni_core/diagnostics.yml` through `coded()`, never a hand-written code.

## Rulings against the spec, for the operator

1. **Part 1's remainder is two plans** (operator, 2026-10-04): this one, and 1c, which moves the code into the stage modules behind the facade, in one transaction per command.
2. **Queueing a job stays with the caller in 1b.**
   - A node whose only work is to queue a job is drawn as a node that *shows*: it waits or passes straight through. These are `family`, `ask`, `suggest`, `readback`, and `resolve` for Spawn.
   - The route or job that performed the command queues the job, as it does today.
   - 1c's async facade moves queueing into handlers, with jobs queued after the commit.
   - *Cost if wrong:* those nodes become acting in 1c, and the binding test grows by them.
3. **In 1b, each step keeps its own transaction.**
   - The dispatcher writes `at` last, compare-and-swap on the `at` it read.
   - A handler that raises leaves the session on its node (spec §8), but writes made by earlier steps of that command stand, as they do today.
   - 1c gives one transaction per command.
   - *Cost if wrong:* a partial write on a failure, exactly as today.
4. **`at` is derived when it is null, not backfilled by SQL.**
   - The migration adds a nullable column.
   - `session.rests_at` derives the node of a row from before `at` from its phase, its pending proposal and its pending turn. Each old phase has a test (spec §8).
   - The first move writes the real node.
   - *Cost if wrong:* a backfill in 1c.
5. **`authoring.move` stays, for tests only.** 27 existing tests use it to put a session in a phase.
   - It still moves by event, and now clears `at`, so the node is derived from the phase it set.
   - A guard holds that nothing under `src/` calls it.
   - 1c moves it into a test helper.
   - *Cost if wrong:* 27 edits in 1c.
6. **The diagram is redrawn where an arrow was a hand-off rather than a move.**
   - `answered` is a new engine node between `reply` and `said` / `left_open` / `stopped`. One command, three outcomes.
   - *Not quite* on the card goes back to `say` (the person says it again).
   - A goal corrected in words goes to `family`.
   - `read_goal → suggest` and `read_goal → failed` are removed: neither is ever taken.
   - `next_gap` leads to `readback`, then to `card`.
   - The sample section gets a second way out: `sample_back → reply`, *the question stays*.
   - `state.TRANSITIONS` is unchanged, and its pin holds.
   - *Cost if wrong:* the picture changes again.
7. **Commands added to the spec's twelve:**
   - `reply_in_words`: typed words answering a question.
   - `settle_step`: today's accept or reject; part 3 replaces it.
   - The four a job sends: `understood`, `asked_back`, `revised`, `provider_failed`.
   - *Cost if wrong:* renames.
8. **A command's own payload is checked before the diagram is asked.** A duplicate answer is still MI0203, an option never offered still MI0205, a value that does not fit still MI0208, as today.
9. **`resolve` rests when a command arrives, and resolves when resumed**, as today:
   - accepting a goal and building it are two calls;
   - Build resumes it in the same request (`start_building`);
   - Spawn resumes it in the build job.
10. **Events stay on the arrows**, and `state.advance` stays in the core, tested. The shell stops calling it. Part 3 decides whether phases still need events.

## Review Focus

1. **A job's completion arriving after the person moved the session on.** Example: the model's provider fails while the person is answering a question. The command is refused by the diagram and ignored, never failing the job or moving the session. Pinned in Task 5.
2. **A session row from before `at`** (null), in each phase. Any command legal from its derived node works, and the first move writes the real node. Pinned in Task 3.
3. **Two commands racing on one session.** The second's write is refused with MI0201, so a session never holds a node it did not reach. Pinned in Task 4.
4. **A command that leaves the session where it was** writes nothing and leaves `row_version` alone. Examples: a sample that answered nothing, typed words being read. Issue 226 found the version moving there. Pinned in Task 4 and Task 6.
5. **A handler that raises.** The session stays on its node. The resolver's own failure still lands on `failed`, and is then raised as today. Pinned in Task 4 and Task 7.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/mendel-authoring/src/mendel_authoring/types.py` | six more commands |
| Modify `packages/mendel-authoring/src/mendel_authoring/protocol.py` | return arrows share a name; a within-request section's ways out; every built node and arrow marked; the redraws |
| Modify `packages/mendel-authoring/src/mendel_authoring/interpret.py` | `follow(returning_to=)`, section exits, `run(command=None)` resumes |
| Modify `packages/mendel-authoring/tests/test_protocol.py`, `test_interpret.py` | the core's tests |
| Modify `packages/mendel-api/src/mendel_api/models.py` | `PipelineAuthoringSession.at` |
| Create `packages/mendel-api/migrations/versions/c9e4b2d71a38_session_at.py` | the column |
| Create `packages/mendel-api/src/mendel_api/services/session.py` | `rests_at`, `handles`, `Ctx`, `allows`, `check`, `perform_now`, `resume` |
| Create `packages/mendel-api/src/mendel_api/stages/__init__.py`, `describe.py`, `gathering.py`, `samples.py`, `building.py` | the handlers |
| Modify `packages/mendel-api/src/mendel_api/services/authoring.py` | each entry point performs; `move` test-only; `_swap` loses `phase` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` | job completions are commands |
| Create `packages/mendel-api/tests/test_authoring_at.py`, `test_authoring_dispatch.py`, `test_authoring_binding.py` | `at`, the dispatcher, the binding and the guards |
| Modify `docs/design/authoring-protocol.md`, `ARCHITECTURE.md`, `docs/design/diagrams/` (generated) | the docs |

There is no `goal.py` stage module: the card's two commands have no acting node in 1b. 1c adds it, with the move.

---

### Task 1: The core learns retry, sections and resuming

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/types.py`, `protocol.py`, `interpret.py`
- Test: `packages/mendel-authoring/tests/test_interpret.py`, `test_protocol.py`

**Interfaces:**
- Produces:
  - `Command.REPLY_IN_WORDS`, `SETTLE_STEP`, `UNDERSTOOD`, `ASKED_BACK`, `REVISED`, `PROVIDER_FAILED`
  - `Protocol.exits(node_id) -> list[Edge]`
  - `interpret.follow(protocol, at, on, *, returning_to: Phase | None = None) -> Edge`
  - `interpret.run(protocol, at, command: str | None, enter, *, returning_to: Phase | None = None, limit=64) -> Ran`. `command=None` resumes: it enters `at` itself.

- [x] **Step 1: Write the failing tests** (append to `test_interpret.py`)

```python
from mendel_authoring.types import Event


def _phased(id, phase, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=phase, built=True, **kw)


RETRYING = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _phased("failed", Phase.FAILED, waits=True),
        _phased("family", Phase.UNDERSTANDING, waits=True),
        _phased("resolve", Phase.RESOLVING, waits=True),
    ),
    edges=(
        Edge(source="failed", target="family", on="retry", event=Event.RETRY, returns=True,
             built=True),
        Edge(source="failed", target="resolve", on="retry", event=Event.RETRY, returns=True,
             built=True),
    ),
)


def test_two_return_arrows_share_the_retry_name_and_the_failure_chooses():
    assert follow(RETRYING, "failed", "retry", returning_to=Phase.RESOLVING).target == "resolve"
    assert follow(RETRYING, "failed", "retry", returning_to=Phase.UNDERSTANDING).target == "family"


SECTIONED = Protocol(
    stages=(Stage(id="s", title="s"), Stage(id="w", title="w", within_request=True)),
    nodes=(
        _n("reply", waits=True), _n("upload", acts=True), _n("next"),
        Node(id="w_in", stage="w", actor=Actor.ENGINE, label="in", phase=Phase.GATHERING,
             built=True),
        Node(id="w_back", stage="w", actor=Actor.ENGINE, label="back", phase=Phase.GATHERING,
             built=True),
    ),
    edges=(
        _e("reply", "upload", Command.UPLOAD_SAMPLE.value), _e("upload", "w_in"),
        _e("w_in", "w_back"), _e("w_back", "next", "answered"), _e("w_back", "reply", "stays"),
    ),
)


def test_a_section_within_a_request_is_one_step_and_its_ways_out_are_the_entry_nodes():
    ran = run(SECTIONED, "reply", Command.UPLOAD_SAMPLE.value, lambda node: "answered")
    assert ran.at == "next" and ran.path == ["upload", "next"]
    stays = run(SECTIONED, "reply", Command.UPLOAD_SAMPLE.value, lambda node: "stays")
    assert stays.at == "reply"


def test_resuming_enters_where_the_session_rests():
    ran = run(GATHER, "next_gap", None, lambda node: {"next_gap": "a_gap"}.get(node))
    assert ran.at == "ask" and ran.path == ["next_gap", "ask"]
```

Append to `test_protocol.py`:

```python
def test_the_ways_out_of_a_section_are_named_once_each():
    with pytest.raises(ValueError, match="ways out of section"):
        Protocol(
            stages=(Stage(id="s", title="s"), Stage(id="w", title="w", within_request=True)),
            nodes=(_taking("a", acts=True), _taking("b"), _taking("c"),
                   Node(id="w1", stage="w", actor=Actor.ENGINE, label="w1",
                        phase=Phase.GATHERING, built=True)),
            edges=(p.Edge(source="a", target="w1", built=True),
                   p.Edge(source="w1", target="b", on="answered", built=True),
                   p.Edge(source="w1", target="c", built=True)),
        )
```

In `test_protocol.py`, update `test_the_commands_are_the_specs` to the eighteen values: the twelve, plus `reply_in_words`, `settle_step`, `understood`, `asked_back`, `revised` and `provider_failed`. Rename it `test_the_commands_are_the_specs_and_1bs`.

- [x] **Step 2: Run them; expected FAIL**

`uv run pytest packages/mendel-authoring -q`

Expected:
- `follow() got an unexpected keyword argument 'returning_to'`;
- the section test refused on `'answered'`;
- `run` refusing `None`;
- no ValueError for the unnamed way out;
- the command set differing.

- [x] **Step 3: Implement**

`types.py`, at the end of `Command`:

```python
    REPLY_IN_WORDS = "reply_in_words"
    """Typed words answering a question: a model reads them into a suggestion. Nothing moves."""
    SETTLE_STEP = "settle_step"
    """Accept or reject a step's proposal, as today. Part 3 replaces it with `continue`,
    `choose` and `answer_fact`."""
    # **A job's completion is a command** (spec §3.2): each names an arrow out of where the job's
    # session waits, and is refused, so ignored, once the session has moved on.
    UNDERSTOOD = "understood"
    ASKED_BACK = "asked_back"
    REVISED = "revised"
    PROVIDER_FAILED = "provider_failed"
```

`protocol.py`, in `_consistent`, change the `named` line so return arrows may share a name (their target is chosen by the failure, `failed_from`):

```python
            named = [e.on for e in out if e.on is not None and not e.returns]
```

Then, after the within-request event check, add:

```python
        for stage in self.stages:
            if not stage.within_request:
                continue
            leaving = [
                e.on for e in self.edges
                if e.built and nodes[e.source].stage == stage.id
                and nodes[e.target].stage != stage.id
            ]
            if any(on is not None for on in leaving) and (
                None in leaving or len(set(leaving)) != len(leaving)
            ):
                raise ValueError(f"the ways out of section {stage.id} need a name each, once")
```

And a method on `Protocol`:

```python
    def exits(self, node_id: str) -> list[Edge]:
        """The ways out of the within-request section `node_id` leads into, if it leads into one.

        **A section within a request is one step** (14.7.8.1): the node entering it acts, runs
        the section's steps inside its request, and its outcome names a way *out* of the
        section. The steps inside are drawn so the card and the picture share ids, and are never
        run by the interpreter."""
        within = {s.id for s in self.stages if s.within_request}
        stage_of = {n.id: n.stage for n in self.nodes}
        into = {stage_of[e.target] for e in self.edges if e.built and e.source == node_id}
        if len(into) != 1 or not into <= within or stage_of.get(node_id) in into:
            return []
        (section,) = into
        return [
            e for e in self.edges
            if e.built and stage_of[e.source] == section and stage_of[e.target] != section
        ]
```

`interpret.py`. Import `Phase` from `mendel_authoring.types`. Then:

```python
def follow(
    protocol: Protocol, at: str, on: str | None, *, returning_to: Phase | None = None
) -> Edge:
    """The built arrow out of `at` that `on` names; `None` names the one way straight on.

    Out of a node that enters a within-request section, the section's ways out are its own. Of
    several return arrows, the one back to `returning_to`, the phase that failed, is taken."""
    found = [e for e in protocol.edges if e.built and e.source == at and e.on == on]
    if not found:
        found = [e for e in protocol.exits(at) if e.on == on]
    if len(found) > 1 and returning_to is not None:
        phase = {n.id: n.phase for n in protocol.nodes}
        found = [e for e in found if not e.returns or phase[e.target] is returning_to]
    if not found:
        named = "the way straight on" if on is None else repr(on)
        raise Refused(coded("MI0216", f"from {at!r}, nothing leads on by {named}"))
    return found[0]
```

In `run`, take `command: str | None` and `returning_to: Phase | None = None`, and replace its first two lines:

```python
    nodes: dict[str, Node] = {n.id: n for n in protocol.nodes}
    if command is None:
        # **Resuming** (14.7.8.1): the session is entered where it rests, as if just arrived.
        node = nodes[at]
    else:
        node = nodes[follow(protocol, at, command, returning_to=returning_to).target]
    path = [node.id]
```

Update `run`'s docstring: *`command=None` resumes: `at` itself is entered.*

- [x] **Step 4: Run them; expected PASS.** `uv run pytest packages/mendel-authoring -q`. The real protocol still loads: no node in it takes part yet.

- [x] **Step 5: `make check`, then commit.** `feat(authoring): retry chooses by the failure, a section is one step, and a session can be resumed (#136)`

---

### Task 2: The protocol, marked — and redrawn where it was not a move

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/protocol.py` (`PROTOCOL` only)
- Test: `packages/mendel-authoring/tests/test_protocol.py`
- Regenerate: `docs/design/diagrams/authoring-protocol.md`

**Interfaces:**
- Produces: the marked protocol, which Tasks 4–8 run.
  - Built **acting** nodes: `read_goal`, `list_needs`, `next_gap`, `answered`, `upload`, `resolve`, `offer`.
  - Built **waiting** nodes: `say`, `family`, `reply`, `card`, `resolve`, `step_settled`, `step_rule`, `step_choice`, `done`, `failed`.
  - The outcome names, by node:
    - `read_goal`: `want_returned`
    - `list_needs`: `listed`, `unreachable`
    - `next_gap`: `a_gap`, `nothing_missing`
    - `answered`: `said`, `left_open`, `no_input`
    - `upload`, through the sample section's ways out: `answered`, `stays`
    - `resolve`: `stored`, `cant_build`
    - `offer`: `settled`, `a_rule`, `no_rule`, `nothing_left`, `goal_changed`

- [x] **Step 1: Write the failing tests** (append to `test_protocol.py`)

```python
from mendel_authoring.interpret import Refused, follow

WAITS = {"say", "family", "reply", "card", "resolve", "step_settled", "step_rule",
         "step_choice", "done", "failed"}
ACTS = {"read_goal", "list_needs", "next_gap", "answered", "upload", "resolve", "offer"}


def _main():
    return {n.id: n for n in p.PROTOCOL.nodes if n.built and n.stage != "sample"}


def test_each_built_node_acts_waits_or_passes_as_drawn():
    nodes = _main()
    assert {i for i, n in nodes.items() if n.waits} == WAITS
    assert {i for i, n in nodes.items() if n.acts} == ACTS


def test_every_named_arrow_is_taken_by_its_name():
    """Spec §9: every arrow of the protocol taken once, in a table."""
    named = [e for e in p.PROTOCOL.edges if e.built and e.on is not None
             and not e.source.startswith("sample_")]
    assert len(named) > 30, "the table is suspiciously short"
    phase = {n.id: n.phase for n in p.PROTOCOL.nodes}
    for edge in named:
        back = phase[edge.target] if edge.returns else None
        assert follow(p.PROTOCOL, edge.source, edge.on, returning_to=back) is edge, edge


def test_a_sample_leaves_its_section_answered_or_stays_on_the_question():
    assert follow(p.PROTOCOL, "upload", "answered").target == "next_gap"
    assert follow(p.PROTOCOL, "upload", "stays").target == "reply"


def test_every_other_command_is_refused_where_a_session_waits():
    for node in WAITS:
        drawn = {e.on for e in p.PROTOCOL.edges if e.built and e.source == node}
        for command in Command:
            if command.value not in drawn:
                with pytest.raises(Refused, match="MI0216"):
                    follow(p.PROTOCOL, node, command.value)


def test_a_node_that_neither_acts_nor_waits_passes_straight_on_or_ends():
    for node in _main().values():
        if node.acts or node.waits:
            continue
        out = [e for e in p.PROTOCOL.edges if e.built and e.source == node.id]
        assert len(out) <= 1 and all(e.on is None for e in out), node.id


def test_the_redrawn_arrows():
    edges = {(e.source, e.target, e.on) for e in p.PROTOCOL.edges if e.built}
    assert ("reply", "answered", "answer_gap") in edges
    assert {("answered", "said", "said"), ("answered", "left_open", "left_open"),
            ("answered", "stopped", "no_input")} <= edges
    assert ("card", "say", "revise_goal") in edges and ("card", "family", "revised") in edges
    assert ("next_gap", "readback", "nothing_missing") in edges
    assert ("sample_back", "reply", "stays") in edges
    assert not {(s, t) for s, t, _ in edges} & {("read_goal", "suggest"),
                                                ("read_goal", "failed"), ("next_gap", "card")}
```

`test_the_machine_did_not_change` stays as it is. The redraw keeps every (phase, event) pair.

- [x] **Step 2: Run them; expected FAIL** (no node acts or waits yet).

- [x] **Step 3: Mark `PROTOCOL`**

In `PROTOCOL.nodes`:

| node | change |
|---|---|
| `say`, `family`, `reply`, `card`, `step_settled`, `step_rule`, `step_choice`, `done`, `failed` | `waits=True` |
| `read_goal`, `list_needs`, `next_gap`, `upload`, `offer` | `acts=True` |
| `resolve` | `acts=True, waits=True` |
| new, after `reply` | `_built("answered", "gather", _ENGINE, "Your answer:<br/>said, open, or missing?", _P.GATHERING, shape=Shape.CHOICE, acts=True)` |

In `PROTOCOL.edges`, each built arrow becomes the one below. Labels and events are unchanged unless shown. `_move` takes `on=` through `**kw`, as `_e` does.

```python
        # ① describe
        _e("say", "family", on="describe", built=True),
        _e("family", "read_goal", "each family, whole", on="understood", built=True),
        _e("family", "say", "none fits: it asks you", on="asked_back", built=True),
        _move("family", "failed", _E.PROVIDER_FAILED, "model failed", on="provider_failed"),
        _move("read_goal", "list_needs", _E.WANT_RETURNED, on="want_returned"),
        _move("list_needs", "say", _E.WANT_UNREACHABLE, "nothing makes it: it asks you",
              on="unreachable"),
        # ② gather
        _e("list_needs", "next_gap", on="listed", built=True),
        _e("next_gap", "ask", "yes", on="a_gap", built=True),
        _e("ask", "reply", built=True),
        _e("reply", "suggest", "typed in your words", on="reply_in_words", built=True),
        _e("suggest", "reply", "you confirm with a click", built=True),
        _e("reply", "answered", on="answer_gap", built=True),
        _e("answered", "said", "I know it", on="said", built=True),
        _e("answered", "left_open", "can't share it", on="left_open", built=True),
        _move("answered", "stopped", _E.INPUT_UNAVAILABLE, "I don't have that input",
              on="no_input"),
        _move("said", "next_gap", _E.FACT_ADDED),
        _move("left_open", "next_gap", _E.FACT_ADDED),
        _e("reply", "upload", "upload a sample (when something here reads it)",
           on="upload_sample", built=True),
        _e("upload", "sample_level", "uploaded", built=True),
        *_SAMPLE_EDGES,
        _e("sample_back", "next_gap", "answered", on="answered", built=True),
        _e("sample_back", "reply", "the question stays", on="stays", built=True),
        # ③ check
        _move("next_gap", "readback", _E.NOTHING_MISSING, "nothing unknown",
              on="nothing_missing"),
        _e("readback", "card", "in the AI's words", built=True),
        _move("card", "resolve", _E.GOAL_ACCEPTED, "that's right", on="confirm_goal"),
        _move("card", "say", _E.GOAL_REVISED, "not quite", on="revise_goal"),
        _move("card", "family", _E.GOAL_REVISED, "corrected in your words", on="revised"),
        # ④ build
        _move("resolve", "offer", _E.BLUEPRINT_STORED, on="stored"),
        _move("resolve", "failed", _E.BUILD_FAILED, "can't build it", on="cant_build"),
        _move("resolve", "failed", _E.PROVIDER_FAILED, "model failed", on="provider_failed"),
        _e("offer", "step_settled", "settled", on="settled", built=True),
        _e("offer", "step_rule", "a rule decided", on="a_rule", built=True),
        _e("offer", "step_choice", "no rule could", on="no_rule", built=True),
        _move("step_settled", "offer", _E.PROPOSAL_SETTLED, on="settle_step"),
        _move("step_rule", "offer", _E.PROPOSAL_SETTLED, on="settle_step"),
        _move("step_choice", "offer", _E.PROPOSAL_SETTLED, "you choose", on="settle_step"),
        _move("offer", "done", _E.NOTHING_LEFT, "nothing left", on="nothing_left"),
        _move("offer", "resolve", _E.GOAL_ACCEPTED, "the goal changed", on="goal_changed"),
        _move("done", "resolve", _E.GOAL_ACCEPTED, "the goal changed", on="confirm_goal"),
        # when it goes wrong
        _move("failed", "family", _E.RETRY, "retry", returns=True, on="retry"),
        _move("failed", "resolve", _E.RETRY, "retry", returns=True, on="retry"),
```

**Removed:** `read_goal → suggest`, `read_goal → failed`, `next_gap → card`, `reply → said`, `reply → left_open` and `reply → stopped`. The last three are now `answered`'s arrows.

The planned edges (`resolve → plan` and the rest) and the sample section's inner edges are unchanged.

If the validator refuses the result, read its message. It names the node and the rule. Fix the marking, never the validator.

Above the edges, a comment: *Every arrow a session takes is named: a command out of a waiting node, an outcome out of an acting one (14.7.8.1). `offer → resolve` (the goal changed) is drawn and is returned by no handler today: a goal card cannot be pending while a step is.*

- [x] **Step 4: Run them; expected PASS.**

```bash
uv run pytest packages/mendel-authoring -q
uv run python tools/generate_protocol_doc.py
uv run python tools/generate_protocol_doc.py --check
```

In the generated mermaid:
- `answered` sits in ② between `reply` and `said`;
- the card has two arrows back;
- nothing is drawn twice.

- [x] **Step 5: `make check`, then commit.** `feat(authoring): every arrow a session takes is named, and the diagram is redrawn where an arrow was not a move (#136)`

---

### Task 3: Where a session rests: `at`

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py` (`PipelineAuthoringSession`)
- Create: `packages/mendel-api/migrations/versions/c9e4b2d71a38_session_at.py`
- Create: `packages/mendel-api/src/mendel_api/services/session.py` (`rests_at` only, in this task)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`open_session` writes `at="say"`; `move` clears `at`)
- Test: `packages/mendel-api/tests/test_authoring_at.py`

**Interfaces:**
- Produces:
  - `PipelineAuthoringSession.at: str | None`.
  - `session.rests_at(db, row) -> str`: the stored node, or the node derived from the phase, the pending proposal and the pending turn.

- [x] **Step 1: Write the failing tests** (`test_authoring_at.py`)

```python
"""Where a session rests (14.7.8.1): `at`, and the node derived for a row from before it."""

import secrets

import pytest
from mendel_api.authoring.types import Mode, Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring, session
from mendel_authoring.protocol import PROTOCOL
from sqlalchemy import text


@pytest.fixture
def sid():
    """One session on one draft, the tables emptied first (`test_authoring_service.py`'s way)."""
    with session_scope() as db:
        db.execute(text(
            "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
            "pipeline_authoring_session, pipeline_draft"
        ))
    draft_id = secrets.token_hex(16)
    with session_scope() as db:
        db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                             graph={"nodes": [], "edges": []}, provenance={}, revision=1))
    return authoring.open_session(draft_id, mode=Mode.BUILD, who="tester")


def _at(sid):
    with session_scope() as db:
        return session.rests_at(db, db.get(PipelineAuthoringSession, sid))


def _old(sid, phase: Phase):
    """A row from before `at`: the phase set, `at` null."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.phase, row.at = phase.value, None


def test_a_new_session_rests_where_you_say_what_you_want(sid):
    assert _at(sid) == "say"


@pytest.mark.parametrize("phase, node", [
    (Phase.UNDERSTANDING, "say"), (Phase.GATHERING, "list_needs"),
    (Phase.GOAL_REVIEW, "card"), (Phase.RESOLVING, "resolve"), (Phase.BUILDING, "offer"),
    (Phase.COMPLETE, "done"), (Phase.FAILED, "failed"), (Phase.STOPPED, "stopped"),
])
def test_a_row_from_before_at_rests_on_its_phases_node(sid, phase, node):
    """Spec §8: every old phase has a derived node, and each is a built one."""
    _old(sid, phase)
    assert _at(sid) == node
    assert node in {n.id for n in PROTOCOL.nodes if n.built}


def test_a_pending_turn_in_understanding_rests_where_the_model_works(sid):
    authoring.say(sid, "RNA-seq counts")
    _old(sid, Phase.UNDERSTANDING)
    assert _at(sid) == "family"


def test_a_pending_question_rests_on_the_reply(sid):
    _old(sid, Phase.GATHERING)
    authoring.propose(sid, kind=authoring.GAP, payload={"subject": "x", "kind": "input",
                                                        "why": "", "options": {}, "block": {}})
    assert _at(sid) == "reply"


@pytest.mark.parametrize("tier, node", [(1, "step_settled"), (2, "step_settled"),
                                        (3, "step_rule"), (4, "step_choice")])
def test_a_pending_step_rests_on_its_tiers_card(sid, tier, node):
    _old(sid, Phase.BUILDING)
    authoring.propose(sid, kind=authoring.STEP, payload={"node": "n", "options": {},
                                                         "block": {"tier": tier}})
    assert _at(sid) == node


def test_a_stored_node_wins_over_the_phase(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "family"
    assert _at(sid) == "family"


def test_a_test_moving_by_event_leaves_the_node_to_be_derived(sid):
    """Ruling 5: `move` is setup for tests, and clears `at`."""
    from mendel_authoring import state as st

    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, sid).at is None
    assert _at(sid) == "list_needs"
```

Check the `PipelineDraft` column names against `models.py` before running. Copy them from `test_authoring_service.py`'s `draft` fixture, which writes the same row.

- [x] **Step 2: Run them; expected FAIL.**

`MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_at.py -q`

Expected: `ImportError` on `session` (cannot import name). Apply the migration to the test database once with `MENDEL_DATABASE_URL=… make migrate` after Step 3.

- [x] **Step 3: Implement**

`models.py`, after `failed_from`:

```python
    at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """The protocol node this session rests on (14.7.8.1): `mendel_authoring.protocol`'s id,
    written only by the dispatcher (`services/session.py`). The phase is read off that node.

    **Null on a row from before it existed**, and on a row a test moved by event: the node is
    then derived from the phase, the pending proposal and the pending turn
    (`session.rests_at`), and the first move writes it."""
```

The migration (`down_revision = "d5a1c7e93b20"`, today's head). Write its docstring in the style of `a4c8e1f26b93_gathering_facts.py`, saying why it is nullable (ruling 4):

```python
def upgrade() -> None:
    op.add_column("pipeline_authoring_session", sa.Column("at", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "at")
```

`services/session.py`:

```python
"""Where an authoring session rests, and the one place it moves (14.7.8.1).

**The diagram is the program.** A session sits on a node of `mendel_authoring.protocol.PROTOCOL`
(`at`); a command is an arrow out of it; entering an acting node runs its handler
(`mendel_api.stages`), whose outcome names the arrow on. Nothing else in the shell writes `at`
or the phase: the phase is read off the node the session reaches.
"""

from sqlalchemy import select

from mendel_api.authoring.types import Phase, ProposalState, TurnState
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
)

_BY_PHASE = {
    Phase.UNDERSTANDING: "say",
    Phase.GATHERING: "list_needs",
    Phase.GOAL_REVIEW: "card",
    Phase.RESOLVING: "resolve",
    Phase.BUILDING: "offer",
    Phase.COMPLETE: "done",
    Phase.FAILED: "failed",
    Phase.STOPPED: "stopped",
}
"""The node a row from before `at` rests on, when nothing pending says more (ruling 4)."""

_BY_TIER = {1: "step_settled", 2: "step_settled", 3: "step_rule", 4: "step_choice"}


def rests_at(db, row: PipelineAuthoringSession) -> str:
    """The node `row` rests on: stored, or derived from its phase and what is pending."""
    if row.at is not None:
        return row.at
    phase = Phase(row.phase)
    pending = db.scalar(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == row.id,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    )
    if phase is Phase.UNDERSTANDING and db.scalar(
        select(PipelineAuthoringTurn.seq).where(
            PipelineAuthoringTurn.session_id == row.id,
            PipelineAuthoringTurn.role == "assistant",
            PipelineAuthoringTurn.state == TurnState.PENDING.value,
        )
    ) is not None:
        return "family"
    if phase is Phase.GATHERING and pending is not None and pending.kind == "gap":
        return "reply"
    if phase is Phase.BUILDING and pending is not None and pending.kind == "step":
        return _BY_TIER[int(pending.payload["block"]["tier"])]
    return _BY_PHASE[phase]
```

`authoring.open_session`: add `at="say",` to the `PipelineAuthoringSession(...)` call. `authoring.move`:
- add `at=None` to its `.values(...)`;
- give its docstring a first paragraph: *Setup for tests only (ruling 5 of 14.7.8.1b): nothing under `src/` calls it, which `test_authoring_binding.py` holds. It clears `at`, so the node is derived from the phase it sets.*

- [x] **Step 4: Run them; expected PASS.**

```bash
MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make migrate
MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_at.py packages/mendel-api/tests/test_migrations.py -q
```

- [x] **Step 5: `make verify`, then commit.** `feat(authoring): a session stores the node it rests on (#136)`

---

### Task 4: The dispatcher

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/session.py`
- Create: `packages/mendel-api/src/mendel_api/stages/__init__.py`
- Test: `packages/mendel-api/tests/test_authoring_dispatch.py`

**Interfaces:**
- Consumes:
  - `interpret.run`, `interpret.follow` and `Refused` from Task 1;
  - `rests_at` from Task 3.
- Produces:
  - `session.Ctx(session_id: str, command: str | None, payload: dict, raised: BaseException | None = None)`.
  - `session.handles(node_id: str)`, a decorator registering `Callable[[Ctx], str | None]` in `session.HANDLERS`.
  - `session.allows(session_id, command) -> bool`.
  - `session.check(session_id, command) -> None` (raises `Refused`).
  - `session.perform_now(session_id, command, *, protocol=PROTOCOL, handlers=None, **payload) -> Ran`.
  - `session.resume(session_id, *, protocol=PROTOCOL, handlers=None, **payload) -> Ran`.

- [x] **Step 1: Write the failing tests** (`test_authoring_dispatch.py`)

Use Task 3's `sid` fixture, copied (a test file may not import another's fixtures here). The toy protocol below is the dispatcher's, not the product's. The dispatcher is checked against it so that no handler of the real one is involved.

```python
"""The dispatcher (14.7.8.1): one place a session moves, read off the diagram."""

import pytest
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import session
from mendel_authoring.interpret import Refused
from mendel_authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_authoring.types import Event

# (the `sid` fixture from test_authoring_at.py, copied)


def _n(id, phase, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=phase, built=True, **kw)


TOY = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _n("say", Phase.UNDERSTANDING, waits=True),
        _n("work", Phase.GATHERING, acts=True),
        _n("card", Phase.GOAL_REVIEW, waits=True),
        _n("failed", Phase.FAILED, waits=True),
    ),
    edges=(
        Edge(source="say", target="work", on="describe", event=Event.WANT_RETURNED, built=True),
        Edge(source="work", target="card", on="done", event=Event.NOTHING_MISSING, built=True),
        Edge(source="work", target="say", on="same", event=Event.WANT_UNREACHABLE, built=True),
        Edge(source="work", target="failed", on="broke", event=Event.PROVIDER_FAILED,
             built=True),
    ),
)


def _row(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        return row.at, row.phase, row.row_version, row.failed_from


def test_a_command_moves_the_session_and_the_phase_is_read_off_the_node(sid):
    seen = []

    def work(ctx):
        seen.append((ctx.command, ctx.payload))
        return "done"

    ran = session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work}, said="x")
    assert ran.at == "card" and seen == [("describe", {"said": "x"})]
    at, phase, version, _ = _row(sid)
    assert (at, phase, version) == ("card", Phase.GOAL_REVIEW.value, 2)


def test_a_command_with_no_arrow_is_refused_and_nothing_moves(sid):
    with pytest.raises(Refused, match="MI0216"):
        session.perform_now(sid, "confirm_goal", protocol=TOY, handlers={})
    assert _row(sid)[:3] == ("say", Phase.UNDERSTANDING.value, 1)


def test_a_command_that_leaves_the_session_where_it_was_writes_nothing(sid):
    """Review focus 4, issue 226: the version is not moved by a command that moved nothing."""
    session.perform_now(sid, "describe", protocol=TOY, handlers={"work": lambda ctx: "same"})
    assert _row(sid)[:3] == ("say", Phase.UNDERSTANDING.value, 1)


def test_a_handler_that_raises_leaves_the_session_on_its_node(sid):
    """Spec §8."""
    def work(ctx):
        raise ValueError("no")

    with pytest.raises(ValueError, match="no"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})
    assert _row(sid)[0] == "say"


def test_a_handler_may_hand_back_an_exception_raised_once_the_session_moved(sid):
    """Review focus 5: the resolver's own failure lands on `failed`, and is raised as today."""
    def work(ctx):
        ctx.raised = RuntimeError("resolver broke")
        return "broke"

    with pytest.raises(RuntimeError, match="resolver broke"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})
    at, phase, _, failed_from = _row(sid)
    assert (at, phase, failed_from) == ("failed", "failed", Phase.UNDERSTANDING.value)


def test_a_session_moved_meanwhile_refuses_the_second_write(sid):
    """Review focus 3: the write is compare-and-swap on the node read."""
    def work(ctx):
        with session_scope() as db:
            db.get(PipelineAuthoringSession, sid).at = "card"  # another tab got there first
        return "done"

    with pytest.raises(ValueError, match="MI0201"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})


def test_resuming_enters_the_node_the_session_rests_on(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "work"
    assert session.resume(sid, protocol=TOY, handlers={"work": lambda ctx: "done"}).at == "card"


def test_allows_and_check_read_the_diagram(sid):
    assert session.allows(sid, "describe", protocol=TOY)
    assert not session.allows(sid, "done", protocol=TOY)
    with pytest.raises(Refused, match="MI0216"):
        session.check(sid, "done", protocol=TOY)
```

`authoring.open_session` sets `at="say"` and `row_version=1`, so the toy can start from the real one.

- [x] **Step 2: Run them; expected FAIL** (`AttributeError: module 'mendel_api.services.session' has no attribute 'perform_now'`).

- [x] **Step 3: Implement** (append to `session.py`; the imports join the existing ones)

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_authoring import interpret
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL, Protocol
from sqlalchemy import update

from mendel_api.db import session_scope


@dataclass
class Ctx:
    """What a handler is handed: the session, what arrived (`None` when resumed), its payload,
    and an exception to raise once the session has moved (`raised`, for `resolve`)."""

    session_id: str
    command: str | None
    payload: dict = field(default_factory=dict)
    raised: BaseException | None = None


Handler = Callable[[Ctx], str | None]
HANDLERS: dict[str, Handler] = {}
"""Each acting node's handler, by node id. `test_authoring_binding.py` holds this to the
protocol's acting nodes, both ways."""


def handles(node_id: str) -> Callable[[Handler], Handler]:
    def register(handler: Handler) -> Handler:
        if node_id in HANDLERS:
            raise ValueError(f"{node_id} already has a handler: {HANDLERS[node_id].__name__}")
        HANDLERS[node_id] = handler
        return handler

    return register


def _bound() -> dict[str, Handler]:
    import mendel_api.stages  # noqa: F401 — importing the stage modules registers them

    return HANDLERS


def _where(session_id: str) -> tuple[str, str | None, Phase, Phase | None]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        came_from = Phase(row.failed_from) if row.failed_from else None
        return rests_at(db, row), row.at, Phase(row.phase), came_from


def allows(session_id: str, command: str, *, protocol: Protocol = PROTOCOL) -> bool:
    try:
        check(session_id, command, protocol=protocol)
    except interpret.Refused:
        return False
    return True


def check(session_id: str, command: str, *, protocol: Protocol = PROTOCOL) -> None:
    """Refuse (MI0216) a command that names no arrow from where the session rests."""
    at, _, _, came_from = _where(session_id)
    interpret.follow(protocol, at, command, returning_to=came_from)


def perform_now(
    session_id: str,
    command: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    **payload: object,
) -> interpret.Ran:
    """Take `command`'s arrow from where the session rests, run every handler on the way, and
    write where it comes to rest."""
    return _dispatch(session_id, command, payload, protocol, handlers)


def resume(
    session_id: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    **payload: object,
) -> interpret.Ran:
    """Enter the node the session rests on, as if it had just arrived."""
    return _dispatch(session_id, None, payload, protocol, handlers)


def _dispatch(session_id, command, payload, protocol, handlers) -> interpret.Ran:
    bound = _bound() if handlers is None else handlers
    start, stored, phase, came_from = _where(session_id)
    ctx = Ctx(session_id, command, dict(payload))
    ran = interpret.run(
        protocol, start, command, lambda node: bound[node](ctx), returning_to=came_from
    )
    if ran.at != start:
        node = next(n for n in protocol.nodes if n.id == ran.at)
        failed = st.failed_from(phase).value if node.phase is Phase.FAILED else None
        with session_scope() as db:
            done = db.execute(
                update(PipelineAuthoringSession)
                .where(
                    PipelineAuthoringSession.id == session_id,
                    PipelineAuthoringSession.at.is_not_distinct_from(stored),
                )
                .values(
                    at=ran.at,
                    phase=node.phase.value,
                    failed_from=failed,
                    row_version=PipelineAuthoringSession.row_version + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            if done.rowcount != 1:
                raise ValueError(
                    coded("MI0201", "this session moved while you were looking at it")
                    + f"\n  it was at {start} when {command or 'resuming'} arrived"
                    + "\n  re-read it before acting on it"
                )
    if ctx.raised is not None:
        raise ctx.raised
    return ran
```

`stages/__init__.py`:

```python
"""The handlers, one module per section of the protocol (14.7.8.1). Importing this package
registers them (`services.session.handles`); 1c moves each section's code in beside them."""
```

Two cautions:
- The race test's handler writes `at` inside the dispatch, so the CAS sees a changed `at`. If `is_not_distinct_from` is not available on the column in this SQLAlchemy, use `(PipelineAuthoringSession.at == stored) if stored is not None else PipelineAuthoringSession.at.is_(None)`.
- **A stored `None`, with a derived start, is still the CAS's value**: two racers on a derived row are told apart by the first one writing a node.

- [x] **Step 4: Run them; expected PASS.**

`MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_authoring_dispatch.py -q`

- [x] **Step 5: `make check`, then commit.** `feat(authoring): the dispatcher — a session moves only by an arrow of the diagram (#136)`

---

### Task 5: ① and ③ — saying it, the model's reading, the card

**Files:**
- Create: `packages/mendel-api/src/mendel_api/stages/describe.py`
- Modify: `packages/mendel-api/src/mendel_api/stages/__init__.py` (import it)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`say`, `decide_goal`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (`_understand`, `_ask_which_result`, `_follow_up`, `_refused`)
- Test: `packages/mendel-api/tests/test_authoring_dispatch.py` (append)

**Interfaces:**
- Consumes: `session.perform_now`, `allows`, `check`, `handles`, `Ctx` from Task 4.
- Produces: the `read_goal` handler. `say` performs `describe` or `reply_in_words` where the diagram draws one.

- [x] **Step 1: Write the failing tests** (append; reuse `sid` and `_row`)

```python
from mendel_api.services import authoring, authoring_jobs
from mendel_authoring.types import Command


def test_saying_what_you_want_moves_to_where_the_model_works(sid):
    authoring.say(sid, "RNA-seq counts")
    assert _row(sid)[:2] == ("family", Phase.UNDERSTANDING.value)


def test_the_models_reading_is_a_command_that_runs_to_the_first_question(sid):
    authoring.say(sid, "RNA-seq counts")
    ran = session.perform_now(
        sid, Command.UNDERSTOOD.value,
        goal={"want": ["counts.matrix"], "constraints": {}, "suggested": {}, "stated": []},
    )
    assert ran.path[:3] == ["read_goal", "list_needs", "next_gap"]
    assert _row(sid)[1] == Phase.GATHERING.value


def test_a_provider_failure_after_the_session_moved_on_is_ignored(sid):
    """Review focus 1: the job's command has no arrow from the question; nothing moves."""
    authoring.say(sid, "RNA-seq counts")
    session.perform_now(sid, Command.UNDERSTOOD.value,
                        goal={"want": ["counts.matrix"], "constraints": {}, "suggested": {},
                              "stated": []})
    before = _row(sid)
    authoring_jobs._failed(sid)
    assert _row(sid) == before
```

`counts.matrix` is a placeholder want: replace it with a type id this registry's gathering tests use. Read `test_authoring_gathering.py`'s `_gathering` call sites. The second and third tests need it to have at least one gap. This is a value to look up, not a decision.

- [x] **Step 2: Run them; expected FAIL** (the session stays at `say`; `_failed` does not exist).

- [x] **Step 3: Implement**

`stages/describe.py`:

```python
"""① You describe it: the model's reading becomes the want (14.7.8.1)."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles


@handles("read_goal")
def read_goal(ctx: Ctx) -> str:
    """Store the want the model read; the engine takes over to gather what it needs."""
    authoring.store_goal(ctx.session_id, ctx.payload["goal"])
    return "want_returned"
```

In `services/authoring.py`, add `store_goal`. It is the `goal=` half of each `move(…, goal=…)` it replaces (the want the model read, the confirmed goal, and `None` when nothing makes the want):

```python
def store_goal(session_id: str, goal: dict | None) -> None:
    """The session's goal: the want the model read until the card composes one (14.7.3), then the
    confirmed goal. No move: the dispatcher moves the session (14.7.8.1)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        row.goal = goal
        row.row_version += 1
```

`say` (the service function): after the `with` block, before `return seq + 1`, add:

```python
    # **Typed words are a command only where the diagram draws one** (14.7.8.1): what you want
    # at `say`, an answer at `reply`. Anywhere else they are a chat turn, which moves nothing.
    for typed in (Command.DESCRIBE, Command.REPLY_IN_WORDS):
        if session_mod.allows(session_id, typed.value):
            session_mod.perform_now(session_id, typed.value)
            break
```

Import `from mendel_api.services import session as session_mod`, because `session` is already a local name in this module, and `from mendel_authoring.types import Command`.

`decide_goal`. Before `outcome = decide(...)`, check the arrow:

```python
    session_mod.check(
        session_id,
        (Command.CONFIRM_GOAL if decision is ProposalState.ACCEPTED else Command.REVISE_GOAL).value,
    )
```

Then replace its two `move(...)` returns:

```python
    if decision is ProposalState.ACCEPTED:
        store_goal(session_id, goal)
        session_mod.perform_now(session_id, Command.CONFIRM_GOAL.value)
    else:
        session_mod.perform_now(session_id, Command.REVISE_GOAL.value)
    return outcome, current_phase(session_id)
```

Delete the `version = …` read the moves needed.

`authoring_jobs.py`:
- **`_understand`, the end.** Replace the `authoring.move(…WANT_RETURNED…)` and the `authoring.offer_next_gap(session_id)` after it with one `_perform(session_id, Command.UNDERSTOOD, goal={…the same dict…})`.
- **`_understand`, the `understood.questions` early return.** Before the `return`, add `_perform(session_id, Command.ASKED_BACK)`.
- **`_ask_which_result`.** At the end, `_perform(session_id, Command.ASKED_BACK)`.
- **`_follow_up`'s revise branch.** Replace `authoring.move(…GOAL_REVISED…)` with `_perform(session_id, Command.REVISED)`.
- **`_refused`.** Replace the `if (phase, …) in st.TRANSITIONS: authoring.move(…)` block with `_failed(session_id)`.

The helpers:

```python
def _perform(session_id: str, command: Command, **payload) -> None:
    """A job's completion is a command (spec §3.2). **Refused means the session moved on**
    while the model worked, and the completion is ignored (spec §8), never a failed job."""
    try:
        session_mod.perform_now(session_id, command.value, **payload)
    except Refused as refused:
        log.info("%s for %s ignored: %s", command.value, session_id, str(refused).splitlines()[0])


def _failed(session_id: str) -> None:
    """The model could not be reached. The session fails only where the diagram draws it."""
    _perform(session_id, Command.PROVIDER_FAILED)
```

Imports:
- `from mendel_api.services import session as session_mod`, as in `authoring.py`: the name `session` is too easily a local here;
- `from mendel_authoring.interpret import Refused`;
- `from mendel_authoring.types import Command`.

Delete the `_version` helper once nothing uses it.

`stages/__init__.py`: add `from mendel_api.stages import describe  # noqa: F401`.

- [x] **Step 4: Run them; expected PASS**, then the authoring suites:

`MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests -q -k "authoring or characteris or inspect"`

Expected: as before this task. A failure is either:
- a moved refusal order, which goes to the command's own checks (ruling 8); or
- a test relying on a hand-written move, which is a defect in this task, not in the test.

- [x] **Step 5: `make check`, then commit.** `refactor(authoring): ① and ③ move by the diagram — typed words, the model's reading, the card (#136)`

---

### Task 6: ② — gathering and samples

**Files:**
- Create: `packages/mendel-api/src/mendel_api/stages/gathering.py`, `stages/samples.py`
- Modify: `stages/__init__.py`, `services/authoring.py` (`offer_next_gap`, `answer_gap`, `_record_found`, `answer_with_sample`, `answer_with_reading`)
- Test: `packages/mendel-api/tests/test_authoring_dispatch.py` (append)

**Interfaces:**
- Produces:
  - handlers `list_needs`, `next_gap`, `answered` and `upload`;
  - `offer_next_gap(session_id)` is `session.resume` and returns the pending proposal's id, or `None`, as before.

- [x] **Step 1: Write the failing tests** (append)

```python
def _gathering(sid):
    authoring.say(sid, "RNA-seq counts")
    session.perform_now(sid, Command.UNDERSTOOD.value,
                        goal={"want": ["counts.matrix"], "constraints": {}, "suggested": {},
                              "stated": []})


def test_an_answer_runs_through_answered_to_the_next_question(sid):
    _gathering(sid)
    pending = authoring.pending_id(sid)
    authoring.answer_gap(pending, "have_it", None, by="tester")
    assert _row(sid)[0] in {"reply", "card"}
    assert authoring.pending_id(sid) != pending


def test_typed_words_on_a_question_leave_the_session_and_its_version(sid):
    """Review focus 4: `reply_in_words` passes through `suggest` back to `reply`."""
    _gathering(sid)
    before = _row(sid)
    authoring.say(sid, "I have them")
    assert _row(sid) == before


def test_a_sample_that_answered_nothing_moves_nothing(sid):
    """Review focus 4, issue 226."""
    _gathering(sid)
    before = _row(sid)
    session.perform_now(sid, Command.UPLOAD_SAMPLE.value, answered=False)
    assert _row(sid) == before
```

Use the same want as Task 5. If its first gap is not an input, use that gap's first option instead of `have_it`: read it from `authoring.read(sid)["pending_proposal"]["payload"]["options"]`.

- [x] **Step 2: Run them; expected FAIL** (no `answered` or `list_needs` handler: `KeyError`).

- [x] **Step 3: Implement**

**Split `offer_next_gap`** into two functions in `services/authoring.py`, without changing any line of what they write:

- `need_listed(session_id) -> bool`. The `gaps.Unreachable` branch: the engine turn, then clearing the goal (`store_goal(session_id, None)` in place of `move(…WANT_UNREACHABLE, goal=None)`). Returns `False`. Otherwise `True`.
- `offer_gap_or_card(session_id) -> str`. The rest:
  - the goal card: its `propose(...)`, then `"nothing_missing"`, with the `move(…NOTHING_MISSING…)` deleted;
  - otherwise the gap: its `propose(...)`, then `"a_gap"`.

Then:

```python
def offer_next_gap(session_id: str) -> str | None:
    """Offer the next thing the want needs, or the goal card when nothing is missing — by
    resuming the session where it rests (`list_needs` or `next_gap`, 14.7.8.1).

    Returns the pending proposal's id, or `None` when nothing can make the want and the person
    was asked again (#202)."""
    ran = session_mod.resume(session_id)
    return pending_id(session_id) if ran.at in {"reply", "card"} else None
```

`stages/gathering.py`:

```python
"""② The engine gathers what it needs (14.7.8.1)."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles


@handles("list_needs")
def list_needs(ctx: Ctx) -> str:
    return "listed" if authoring.need_listed(ctx.session_id) else "unreachable"


@handles("next_gap")
def next_gap(ctx: Ctx) -> str:
    return authoring.offer_gap_or_card(ctx.session_id)


@handles("answered")
def answered(ctx: Ctx) -> str:
    """Which of the three the answer was: `answer_gap` recorded it, and says which."""
    return str(ctx.payload["answered"])
```

`stages/samples.py`:

```python
"""②a Inside: reading a sample. The section runs inside its request (or the reading's job);
`upload` is the one step the interpreter sees, and its outcome is the section's way out."""

from mendel_api.services.session import Ctx, handles


@handles("upload")
def upload(ctx: Ctx) -> str:
    return "answered" if ctx.payload["answered"] else "stays"
```

`stages/__init__.py`: import `gathering` and `samples` as well.

**`answer_gap`** keeps its order. First the payload checks, unchanged: proposal, kind, option, `UPLOAD`, value, settlement. Then:

```python
        session_mod.check(proposal.session_id, Command.ANSWER_GAP.value)
```

Then the recording. Replace `event = …` / `target = st.advance(…)` / `_swap(…, phase=target, …)` with `_swap(db, session_id, row.row_version, facts=facts)`. After the `with`:

```python
    # `_fact_for` decides what an answer means, so it decides the arrow too: *I have it, but
    # can't share it* is still having the input (`said`), *not sure* is `left_open`.
    if stops:
        kind_of = "no_input"
    elif _fact_for(kind, subject, option, value).source is FactSource.OPEN:
        kind_of = "left_open"
    else:
        kind_of = "said"
    session_mod.perform_now(session_id, Command.ANSWER_GAP.value, answered=kind_of)
```

Keep the `stops` note after it, as today, and replace the trailing `offer_next_gap(session_id)` (the dispatcher ran it) with `return current_phase(session_id)`.

**`_swap`** loses its `phase` parameter and the `phase=…` and `failed_from=None` values it wrote. Its callers that passed `phase=Phase.BUILDING` or `COMPLETE` are Task 7's; for this task, leave them passing it and give `_swap` `phase: Phase | None = None`, writing it only when given. Task 7 removes the parameter.

**`_record_found`**: delete `target = …` and `target = st.advance(…)`, and write `_swap(db, session_id, row.row_version, facts=facts)`.

**`answer_with_sample`** and **`answer_with_reading`**: replace `if answered: offer_next_gap(session_id)` with:

```python
    try:
        session_mod.perform_now(session_id, Command.UPLOAD_SAMPLE.value, answered=answered)
    except Refused:
        # The session moved on while the sample was read (spec §8): what it measured stands,
        # and nothing moves.
        pass
```

- [x] **Step 4: Run them; expected PASS**, then:

`MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests -q -k "authoring or characteris or inspect or upload"`

Expected: as before.

- [x] **Step 5: `make check`, then commit.** `refactor(authoring): ② moves by the diagram — the answers, the questions, a sample's way out (#136)`

---

### Task 7: ④ and retry — resolving, steps, failure

**Files:**
- Create: `packages/mendel-api/src/mendel_api/stages/building.py`
- Modify: `stages/__init__.py`, `services/authoring.py` (`start_building`, `settle_step`, `retry`, `_swap`)
- Test: `packages/mendel-api/tests/test_authoring_dispatch.py` (append)

**Interfaces:**
- Produces:
  - handlers `resolve` and `offer`;
  - `start_building` is `session.resume`, and returns the first proposal's id as before.

- [x] **Step 1: Write the failing tests** (append)

```python
def _confirmed(sid):
    from mendel_authoring import state as st

    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring.move(sid, st.Event.NOTHING_MISSING, row_version=2)
    authoring.move(sid, st.Event.GOAL_ACCEPTED, row_version=3,
                   goal={"have": [], "want": ["counts.matrix"]})


def test_a_command_arriving_at_resolve_rests_there(sid):
    """Ruling 9: accepting a goal and building it are two calls."""
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "card"
    calls = []
    from mendel_api.stages import building

    original = building.resolve

    def spy(ctx):
        calls.append(ctx.command)
        return original(ctx)

    session.perform_now(sid, Command.CONFIRM_GOAL.value,
                        handlers={**session.HANDLERS, "resolve": spy})
    assert _row(sid)[0] == "resolve" and calls == ["confirm_goal"]


def test_a_resolver_that_crashes_lands_on_failed_and_raises(sid, monkeypatch):
    """Review focus 5."""
    from mendel_api.services import blueprint

    _confirmed(sid)

    def broken(*a, **k):
        raise RuntimeError("resolver broke")

    monkeypatch.setattr(blueprint, "resolve", broken)
    with pytest.raises(RuntimeError, match="resolver broke"):
        authoring.start_building(sid)
    assert _row(sid)[:2] == ("failed", Phase.FAILED.value)


def test_retry_returns_to_the_phase_that_failed(sid, monkeypatch):
    from mendel_api.services import blueprint

    _confirmed(sid)
    monkeypatch.setattr(blueprint, "resolve",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        authoring.start_building(sid)
    phase, seq = authoring.retry(sid)
    assert (phase, seq, _row(sid)[0]) == (Phase.RESOLVING, None, "resolve")
```

`goal=` must be a goal `Goal.model_validate` accepts. Copy one from `test_authoring_building.py`'s `move(…GOAL_ACCEPTED…, goal=…)`. `start_building` imports `bp` (`blueprint` as `bp`): patch the module attribute it calls, `mendel_api.services.blueprint.resolve`, since `bp.resolve` is read at call time.

- [x] **Step 2: Run them; expected FAIL** (no `resolve` handler).

- [x] **Step 3: Implement**

**`start_building`** becomes two parts.
1. **`build_blueprint(session_id, *, client) -> str`** holds today's body, from the first `with` block to the end, with these changes:
   - **The guard at the top.** Delete `st.advance(...)`. In its place:
     ```python
     if session_mod.rests_at(db, row) != "resolve":
         raise ValueError(coded("MI0200", f"there is nothing to build from {row.phase}"))
     ```
   - **The resolver fails.** `except UnroutableError`: keep the `_note(…MI0207)` and `return "cant_build"`, deleting the `move`. `except Exception as failure`: `log.exception(...)` and re-raise. The handler hands it back (below).
   - **The success path.** `_swap(…, phase=Phase.BUILDING, …)` loses `phase`. For an empty blueprint, `_swap(…, phase=Phase.COMPLETE)` is deleted. Return `"stored"` after `_offer(...)`, or after nothing for an empty blueprint.
2. **The public function:**

```python
def start_building(session_id: str, *, client=None) -> str | None:
    """Resolve the whole blueprint, store it, and offer its first step, by resuming the session
    at `resolve` (14.7.8.1). Returns the first proposal's id, or `None` for an empty blueprint.
    (Today's docstring paragraph on why the resolve runs outside a transaction moves to
    `build_blueprint`.)"""
    session_mod.resume(session_id, client=client)
    return pending_id(session_id)
```

`stages/building.py`:

```python
"""④ Your consultant builds it with you (14.7.8.1). Part 3 replaces this stage's handlers."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles

_TIER = {1: "settled", 2: "settled", 3: "a_rule", 4: "no_rule"}


@handles("resolve")
def resolve(ctx: Ctx) -> str | None:
    """**A command arriving rests here; resuming resolves** (ruling 9). Build resumes in the
    same request (`start_building`), Spawn in its build job."""
    if ctx.command is not None:
        return None
    try:
        return authoring.build_blueprint(ctx.session_id, client=ctx.payload.get("client"))
    except ValueError:
        raise  # a coded refusal: nothing moves
    except Exception as failure:  # the resolver itself: `failed`, then raised, as before
        ctx.raised = failure
        return "cant_build"


@handles("offer")
def offer(ctx: Ctx) -> str:
    """Which card the pending step is — or the end. The step was offered by whatever came
    before (`build_blueprint`, `settle_step`)."""
    tier = authoring.pending_step_tier(ctx.session_id)
    return "nothing_left" if tier is None else _TIER[tier]
```

`pending_step_tier(session_id) -> int | None` in `services/authoring.py`: the pending `STEP` proposal's `int(payload["block"]["tier"])`, or `None`.

**`settle_step`.**
- After the payload checks that can refuse without writing, and before `bp.committed`, add `session_mod.check(session_row.id, Command.SETTLE_STEP.value)`. The payload checks are: the registry digest (MI0206 path), `st.settle`, and the option offered.
- Delete `target = st.advance(…)` and `phase=target` in its `_swap`. Keep the cursor.
- The success path's `return StepOutcome(outcome, draft.revision, offered, target)` is inside the `with` block today. Capture `outcome`, `draft.revision`, `offered` and `session_row.id` into locals there instead, and after the block closes:

  ```python
  session_mod.perform_now(settled_in, Command.SETTLE_STEP.value)
  return StepOutcome(outcome, revision_now, offered, current_phase(settled_in))
  ```

  The next step was offered inside the block (`_offer`), so `offer`'s handler finds it pending.
- The MI0206 path's `_swap(…, phase=Phase.BUILDING, …)` loses `phase`: the session never left `building`.

**`retry`.** Replace `target = move(session_id, st.Event.RETRY, row_version=version)` with:

```python
    session_mod.perform_now(session_id, Command.RETRY.value)
    target = current_phase(session_id)
```

**`_swap`**: remove the `phase` parameter, and the `phase=` and `failed_from=None` values.

`stages/__init__.py`: import `building`.

- [x] **Step 4: Run them; expected PASS**, then the whole suite:

`MENDEL_DATABASE_URL=… uv run pytest -q -p no:cacheprovider > /tmp/claude-1000/1b-t7.log; tail -3 /tmp/claude-1000/1b-t7.log`

Expected: as before 1b, plus this plan's new tests.

- [x] **Step 5: `make check`, then commit.** `refactor(authoring): ④ and retry move by the diagram — resolving, steps, failure (#136)`

---

### Task 8: The binding test, and the guards that keep it so

**Files:**
- Create: `packages/mendel-api/tests/test_authoring_binding.py`
- Modify: `tests/fixtures/guard-ledger.md`

- [ ] **Step 1: Write the tests**

```python
"""The diagram and the shell agree (spec §3.2, §9): every acting node has one handler, every
handler an acting node; and nothing but the dispatcher moves a session."""

import ast

from mendel_api.services import session
from mendel_authoring.protocol import PROTOCOL
from support.paths import ROOT

SRC = ROOT / "packages" / "mendel-api" / "src" / "mendel_api"


def test_every_acting_node_has_a_handler_and_every_handler_a_node():
    session._bound()
    acting = {n.id for n in PROTOCOL.nodes if n.built and n.acts}
    assert acting, "no acting node: the comparison would hold vacuously"
    assert set(session.HANDLERS) == acting


def _calls(name: str) -> list[str]:
    found = []
    files = sorted(SRC.rglob("*.py"))
    assert files
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                f = node.func
                called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if called == name:
                    found.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return found


def test_nothing_in_the_shell_calls_advance():
    assert _calls("advance") == []


def test_nothing_in_the_shell_moves_a_session_by_event():
    """Ruling 5: `authoring.move` is setup for tests. Its own definition is not a call."""
    assert [c for c in _calls("move") if c.startswith("services/authoring")] == []


_WRITES = {"values", "PipelineAuthoringSession", "_swap"}
"""The three ways a row's columns are written: an `update(...).values(...)`, the row's
constructor, and `_swap`. A `phase=` on anything else (`AuthoringDecided(phase=…)`) is a
reply carrying the phase, not a write."""


def test_only_the_dispatcher_writes_the_phase():
    writers = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if called in _WRITES and any(k.arg == "phase" for k in node.keywords):
                writers.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert writers, "no writer at all: the scan reads the wrong thing"
    # The dispatcher; `open_session`'s constructor and `move`'s `.values()` (test setup, ruling 5).
    assert {w.split(":")[0] for w in writers} == {"services/session.py",
                                                   "services/authoring.py"}, writers
    assert len([w for w in writers if w.startswith("services/authoring.py")]) == 2, writers
```

`.values()` on other tables (the forge's) never carries `phase=`. If one does, the guard names it, and the fix is to narrow by the table, with the reason written beside it.

`forge_state.py` has its own `move`. The `startswith` keeps it out of the second guard: it moves a forge adaptation, not a session.

- [ ] **Step 2: Run them; expected PASS.** Then **watch each fail**:
1. Delete `@handles("offer")`. Expected: the binding test fails, naming `offer`. Restore it.
2. Add `@handles("say")` to a stub in `stages/describe.py`. Expected: it fails naming `say`. Remove it.
3. Add `st.advance(Phase.BUILDING, st.Event.NOTHING_LEFT)` at the end of `pending_step_tier`'s body, after its return. Expected: `test_nothing_in_the_shell_calls_advance` fails. Remove it.
4. Pass `phase=Phase.BUILDING` to one `_swap` call in `settle_step` (restore the parameter for the duration). Expected: `test_only_the_dispatcher_writes_the_phase` fails, naming the line. Revert.

Record the four in `tests/fixtures/guard-ledger.md` under a new heading *2026-10-04 — the consultant build, 1b*, in the table's columns.

- [ ] **Step 3: `make check`, then commit.** `test(authoring): the binding test — the diagram's acting nodes and the shell's handlers agree (#136)`

---

### Task 9: The docs say so

**Files:** `docs/design/authoring-protocol.md` (*The protocol is code*), `ARCHITECTURE.md` (the `mendel-api` row and the authoring section, if it names `move`), `docs/notes/now.md` (only if it names `move` or `advance`).

- [ ] **Step 1:** In *The protocol is code*, replace the bullet *the state machine is derived* with:

> - **the session moves by it**: a session stores the node it rests on (`at`). Everything a person or a job does is a command naming an arrow out of that node, refused (MI0216) where none is drawn. Entering an acting node runs its handler (`mendel_api/stages/`), whose outcome names the next arrow. The phase is read off the node a session reaches. `services/session.py` is the only code that writes either.

Then update the sentence *To change the protocol, edit `PROTOCOL`*. It now ends: *… and an acting node needs a handler, which the binding test demands.*

Add a changelog line for 14.7.8.1b.

- [ ] **Step 2:** `git grep -n "authoring.move\|st.advance\|\.advance(" -- docs ARCHITECTURE.md CLAUDE.md`, and fix each sentence that describes the shell as moving by event. Leave the journal and archived plans as they are.

- [ ] **Step 3:** `make check`, then commit. `docs: a session moves by the diagram — at, commands, handlers (#136)`

---

## Execution record

*(Filled in while executing.)*
